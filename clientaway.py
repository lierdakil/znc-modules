import znc
import sys

AWAY_DEFAULT_REASON = "Auto away at %time%"

class clientaway(znc.Module):
    description = "Example python3 module for ZNC"
    module_types = [znc.CModInfo.UserModule]

    def GetAwayReason(self):
        sAway = self.GetNV("reason")

        if not sAway:
            sAway = AWAY_DEFAULT_REASON

        return self.ExpandString(sAway)

    def GetAutoAway(self):
        return self.GetNV("autoaway") in ['true', '1', 't', 'y', 'yes']

    def ListCommand(self):
        clients = self.GetUser().GetAllClients()

        output = ['{}\t{}\t{}'.format('Host','Network','Away')]

        for client in clients:
            #output.append('{}\t{}\t{}'.format(client.GetRemoteIP(),client.GetNetwork().GetName(),client.GetAway()))
            output.append('{}\t{}\t{}'.format(client.GetRemoteIP(),client.GetNetwork().GetName(),client.IsAway()))

        self.PutModule('\n'.join(output))

    def SetAwayReasonCommand(self, reason):
        if reason:
            self.SetNV("reason", reason)
            self.PutModule("Away reason set to [{}]".format(reason))

        self.PutModule("Away message will be expanded to [{}]".format(self.GetAwayReason()))

    def AutoAwayCommand(self, message=''):
        if message:
            self.SetNV("autoaway", message)

        if self.GetAutoAway():
            self.PutModule("Auto away when last client goes away or disconnects enabled.")
        else:
            self.PutModule("Auto away when last client goes away or disconnects disabled.")

    def SetAwayCommand(self, sHostname):
        clients = self.GetUser().GetAllClients()

        count = 0

        for client in clients:
            if client.GetRemoteIP() == sHostname:
                client.SetAway(True)
                count+=1

        self.PutModule("{} clients have been set away".format(count))

    def OnModCommand(self, scmd):
        try:
            toks = scmd.split()
            cmd = toks[0].lower()
            args = toks[1:]
            if cmd == 'list':
                self.ListCommand()
            elif cmd == 'reason':
                self.SetAwayReasonCommand(' '.join(args))
            elif cmd == 'autoaway':
                self.AutoAwayCommand(*args)
            elif cmd == 'setaway':
                self.SetAwayCommand(*args)
        except:
            self.PutModule(str(sys.exc_info()[1]))

    def OnClientLogin(self):
        if self.GetAutoAway() and self.GetNetwork() and self.GetNetwork().IsIRCAway():
            self.PutIRC("AWAY")

    def OnClientDisconnect(self):
        if self.GetAutoAway() and self.GetNetwork() and not self.GetNetwork().IsIRCAway() and not self.GetNetwork().IsUserOnline():
            self.PutIRC("AWAY :{}".format(self.GetAwayReason()))

    def OnIRCConnected(self):
        if self.GetAutoAway() and not self.GetNetwork().IsUserOnline():
            self.PutIRC("AWAY :{}".format(self.GetAwayReason()))

    def OnUserRaw(self, sLine):
        sCmd = sLine.s.split()[0]
        sAwayReason = ' '.join(sLine.s.split()[1:])

        if sCmd.lower() == "away":
            if not sAwayReason:
                self.GetClient().SetAway(False)
                self.GetClient().PutClient(":irc.znc.in 305 {} :[Client] You are no longer marked as being away".format(self.GetClient().GetNick()))

                if self.GetNetwork():
                    if self.GetAutoAway() and self.GetNetwork().IsIRCAway():
                        self.PutIRC("AWAY")
            else:
                self.GetClient().SetAway(True)
                self.GetClient().PutClient(":irc.znc.in 306 {} :[Client] You have been marked as being away".format(self.GetClient().GetNick()))

                if self.GetAutoAway() and self.GetNetwork() and not self.GetNetwork().IsIRCAway() and not self.GetNetwork().IsUserOnline():
                    self.PutIRC("AWAY :{}".format(self.GetAwayReason()))

            return znc.HALTCORE

        return znc.CONTINUE
