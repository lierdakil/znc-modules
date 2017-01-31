import znc
import sys
from inspect import signature

AWAY_DEFAULT_REASON = "Auto away at %time%"
TRUE_VALS = ['true', '1', 't', 'y', 'yes']
FALSE_VALS = ['false', '0', 'f', 'n', 'no']

class clientaway(znc.Module):
    description = "Example python3 module for ZNC"
    module_types = [znc.CModInfo.UserModule]

    def GetAwayReason(self):
        sAway = self.GetNV("reason")

        if not sAway:
            sAway = AWAY_DEFAULT_REASON

        return self.ExpandString(sAway)

    def GetAutoAway(self):
        return self.GetNV("autoaway") in TRUE_VALS

    def cmd_list(self):
        '''List clients and their away status'''
        clients = self.GetUser().GetAllClients()

        output = ['{}\t{}\t{}'.format('Host','Network','Away')]

        for client in clients:
            output.append('{}\t{}\t{}'.format(client.GetRemoteIP(),client.GetNetwork().GetName(),client.IsAway()))

        self.PutModule('\n'.join(output))

    def cmd_reason(self, *args):
        '''Set away reason'''
        reason = ' '.join(args)
        if reason:
            self.SetNV("reason", reason)
            self.PutModule("Away reason set to [{}]".format(reason))

        self.PutModule("Away message will be expanded to [{}]".format(self.GetAwayReason()))

    def cmd_autoaway(self, message=''):
        '''Enable or disable autoaway'''
        if message:
            self.SetNV("autoaway", message)

        if self.GetAutoAway():
            self.PutModule("Auto away when last client goes away or disconnects enabled.")
        else:
            self.PutModule("Auto away when last client goes away or disconnects disabled.")

    def cmd_setaway(self, sHostname, sAwayState=''):
        '''Set away status for a client'''
        clients = self.GetUser().GetAllClients()

        count = 0

        for client in clients:
            if client.GetRemoteIP() == sHostname:
                self.setClientAway(sAwayState not in FALSE_VALS, client)
                count+=1

        self.PutModule("{} clients have been modified".format(count))

    def cmd_help(self):
        '''Show this help'''
        cmds = [x[4:] for x in dir(self) if x.startswith('cmd_')]
        for cmd in cmds:
            self.PutModule('{}: {}'.format(cmd, getattr(self, 'cmd_'+cmd, None).__doc__))

    def OnModCommand(self, scmd):
        try:
            toks = scmd.split()
            pCommand = toks[0].lower()
            args = toks[1:]
        except:
            self.PutModule('Invalid command {}'.format(scmd))
            return znc.CONTINUE


        if not pCommand:
            self.PutModule('No command')
            return znc.CONTINUE

        method = getattr(self, 'cmd_' + pCommand.lower(), None)

        if method is None:
            self.PutModule('Invalid command {}'.format(pCommand))
            return znc.CONTINUE

        try:
            method(*args)
        except TypeError as e:
            self.PutModule('Usage: {}{}\n{}'.format(pCommand, signature(method), e))
            return znc.CONTINUE

        return znc.CONTINUE

    def OnClientLogin(self):
        if self.GetAutoAway() and self.GetNetwork() and self.GetNetwork().IsIRCAway():
            self.PutIRC("AWAY")

    def OnClientDisconnect(self):
        if self.GetAutoAway() and self.GetNetwork() and not self.GetNetwork().IsIRCAway() and not self.GetNetwork().IsUserOnline():
            self.PutIRC("AWAY :{}".format(self.GetAwayReason()))

    def OnIRCConnected(self):
        if self.GetAutoAway() and not self.GetNetwork().IsUserOnline():
            self.PutIRC("AWAY :{}".format(self.GetAwayReason()))

    def setClientAway(self, bState, client=None):
        if not client:
            client = self.GetClient()
        if not bState:
            client.SetAway(False)
            client.PutClient(":irc.znc.in 305 {} :[Client] You are no longer marked as being away".format(client.GetNick()))

            if client.GetNetwork():
                if self.GetAutoAway() and client.GetNetwork().IsIRCAway():
                    client.PutIRC("AWAY")
        else:
            client.SetAway(True)
            client.PutClient(":irc.znc.in 306 {} :[Client] You have been marked as being away".format(client.GetNick()))

            if self.GetAutoAway() and client.GetNetwork() and not client.GetNetwork().IsIRCAway() and not client.GetNetwork().IsUserOnline():
                client.PutIRC("AWAY :{}".format(self.GetAwayReason()))

    def OnUserRaw(self, sLine):
        sCmd = sLine.s.split()[0]
        sAwayReason = ' '.join(sLine.s.split()[1:])

        if sCmd.lower() == "away":
            self.setClientAway(sAwayReason)
            return znc.HALTCORE

        return znc.CONTINUE
