import znc

AWAY_DEFAULT_REASON = "Auto away at %time%"

class clientaway(znc.Module):
    description = "Example python3 module for ZNC"
    module_types = [znc.CModInfo.UserModule]

    def GetAwayReason(self):
        sAway = self.GetNV("reason")

        if sAway.empty():
            sAway = AWAY_DEFAULT_REASON

        return self.ExpandString(sAway)

    def GetAutoAway(self):
        return bool(self.GetNV("autoaway"))

    def ListCommand(self, sLine):
        clients = self.GetUser().GetAllClients()

        output = ['{}\t{}\t{}'.format('Host','Network','Away')]

        for client in clients:
            output.append('{}\t{}\t{}'.format(client.GetRemoteIp(),client.GetNetwork().GetName(),client.GetAway()))

        self.PutModule('\n'.join(output))

    def SetAwayReasonCommand(self, sLine):
        reason = ' '.join(sLine.s.split()[1:])

        if reason:
            self.SetNV("reason", reason)
            self.PutModule("Away reason set to [{}]".format(reason))

        self.PutModule("Away message will be expanded to [{}]".format(self.GetAwayReason()))

    def AutoAwayCommand(self, sLine):
        self.SetNV("autoaway", ' '.join(sLine.s.split()[1:]))

        if self.GetAutoAway():
            self.PutModule("Auto away when last client goes away or disconnects enabled.")
        else:
            self.PutModule("Auto away when last client goes away or disconnects disabled.")

    def SetAwayCommand(self, sLine):
        clients = self.GetUser().GetAllClients()

        sHostname = sLine.s.split()[1]
        count = 0

        for client in clients:
            if sHostname or client.GetRemoteIP() == sHostname:
                client.SetAway(True)
                count+=1

        self.PutModule("{} clients have been set away".format(count))

    def onModCommand(self, scmd):
        toks = scmd.s.split()
        cmd = toks[0].lower()
        args = toks[1:]
        if cmd == 'list':
            self.ListCommand('')
        elif cmd == 'reason':
            self.SetAwayReasonCommand(' '.join(args))
        elif cmd == 'autoaway':
            self.AutoAwayCommand(args[0])
        elif cmd == 'setaway':
            self.SetAwayCommand(args[0])

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

        if sCmd == "AWAY":
            if (self.GetClient().IsAway()):
                self.GetClient().SetAway(False)
                self.GetClient().PutClient(":irc.znc.in 305 {} :You are no longer marked as being away".format(self.GetClient().GetNick()))

                if self.GetNetwork():
                    pass #TODO
                    # const vector<CChan*>& vChans = m_pNetwork->GetChans()
                    # vector<CChan*>::const_iterator it
                    #
                    # for (it = vChans.begin(); it != vChans.end(); ++it) {
                    #     // Skip channels which are detached or we don't use keepbuffer
                    #     if (!(*it)->IsDetached() && (*it)->AutoClearChanBuffer()) {
                    #         (*it)->ClearBuffer()
                    #     }
                    # }
                    #
                    # for (CQuery* pQuery : m_pNetwork->GetQueries()) {
                    #     m_pNetwork->DelQuery(pQuery->GetName())
                    # }
                    #
                    # if (GetAutoAway() && m_pNetwork->IsIRCAway()) {
                    #     PutIRC("AWAY")
                    # }
            else:
                self.GetClient().SetAway(True)
                self.GetClient().PutClient(":irc.znc.in 306 {} :You have been marked as being away".format(self.GetClient().GetNick()))

                if self.GetAutoAway() and self.GetNetwork() and not self.GetNetwork().IsIRCAway() and not self.GetNetwork().IsUserOnline():
                    # Use the supplied reason if there was one
                    sAwayReason = ' '.join(sLine.s.split()[1:])

                    if not sAwayReason:
                        sAwayReason = self.GetAwayReason()

                    PutIRC("AWAY :{}".format(sAwayReason))

            return znc.HALTCORE

        return znc.CONTINUE

    def OnRaw(self, sLine):
        # We do the same as ZNC would without the OnRaw hook,
        # except we do not forward 305's or 306's to clients

        sCmd = sLine.Token(1)

        if sCmd == "305":
            self.GetNetwork().SetIRCAway(False)
            return znc.HALTCORE
        elif sCmd == "306":
            self.GetNetwork().SetIRCAway(True)
            return znc.HALTCORE

        return znc.CONTINUE
