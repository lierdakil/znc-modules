#
# ZNC Backlog Module
#
# Allows listing of the backlogs
#
# Copyright (c) 2015 Nikolay Yakimov
# Licensed under the MIT license
#

import sys
import znc
import sqlite3
import re
from functools import reduce
from pyparsing import *
from time import time
from datetime import datetime
from inspect import signature

def cmp(a, b):
    return (a > b) - (a < b)

class backlog(znc.Module):
    description = "Example python3 module for ZNC"
    module_types = [znc.CModInfo.UserModule]

    logstore = None

    def log(self, who, where, message, typ=None):
        if who is not None:
            who = str(who)
        where = str(where)
        message = str(message)
        self.logstore.execute(
            '''INSERT INTO "log" ("who", "where", "message", "type")
               VALUES (?,?,?,?)''',
               (who, where, message, typ))
        self.logstore.commit()

    def OnLoad(self, args, msg):
        dbpath = "{}/log.db".format(self.GetSavePath())
        self.logstore = sqlite3.connect(dbpath)
        c = self.logstore
        # utf-8 aware overloads
        def sqlite_like(template, x):
            if x is None:
                return False
            rx = re.compile(re.escape(template.lower()).replace("_", ".").replace("\\%", ".*?"))
            return rx.match(x.lower()) != None

        def sqlite_nocase_collation(a, b):
            return cmp(a.lower(), b.lower())

        def sqlite_lower(x):
            return x.lower()

        def sqlite_upper(x):
            return x.upper()

        c.create_collation("BINARY", sqlite_nocase_collation)
        c.create_collation("NOCASE", sqlite_nocase_collation)

        c.create_function("LIKE", 2, sqlite_like)
        c.create_function("LOWER", 1, sqlite_lower)
        c.create_function("UPPER", 1, sqlite_upper)
        # end
        c.execute(
           '''CREATE TABLE IF NOT EXISTS "log"
                ( "time" INTEGER NOT NULL DEFAULT CURRENT_TIMESTAMP
                , "who" TEXT
                , "where" TEXT NOT NULL
                , "message" TEXT NOT NULL
                , "type" TEXT
                )''')
        for i in ['time', 'who', 'where', 'type']:
            c.execute(
                '''CREATE INDEX IF NOT EXISTS
                    log_{col}_idx ON log("{col}")'''.format(col=i))
        c.commit()
        return True


    def OnChanMsg(self, nick, channel, message):
        self.log(nick, channel, message.s)
        return znc.CONTINUE

    def OnChanAction(self, nick, channel, message):
        self.log(nick, channel, message.s, 'ACTION')
        return znc.CONTINUE

    def OnPrivMsg(self, nick, message):
        self.log(nick, nick, message.s)
        return znc.CONTINUE

    def OnPrivAction(self, nick, message):
        self.log(nick, nick, message.s, 'ACTION')
        return znc.CONTINUE

    def OnUserMsg(self, tgt, message):
        try:
            command = StringStart() + Suppress(CaselessLiteral('!bl')) + Optional(Word(nums)) + StringEnd()
            res = command.parseString(message.s)
            self.cmd_backlog(tgt, *res)
            return znc.HALT
        except ParseException:
            pass
        except:
            self.PutModule('There was an unexpected error in OnUserMsg: {}'.format(sys.exc_info()))
            return znc.HALT
        self.log(None, tgt, message.s)
        return znc.CONTINUE

    def OnUserAction(self, tgt, message):
        self.log(None, tgt, message.s, 'ACTION')
        return znc.CONTINUE

    def OnModCommand(self, message):
        """Dispatches messages sent to module to command functions."""

        argument = QuotedString(quoteChar='(', endQuoteChar=')', escChar='\\') | Regex(r'(?!--)[^\s]+')
        arguments = ZeroOrMore(argument)
        command = Word(alphas)
        kwarg = command+Suppress(Optional(Literal('=')))+argument
        kwargs = Suppress(Literal('--')) + ZeroOrMore(kwarg.setParseAction(tuple))
        commandWithArgs = StringStart() + command + Group(arguments) + Group(Optional(kwargs)) + StringEnd()

        try:
            pCommand, args, kw = commandWithArgs.parseString(message)
        except ParseException as e:
            self.PutModule('Invalid command {}'.format(e))
            return znc.CONTINUE


        if not pCommand:
            self.PutModule('No command')
            return znc.CONTINUE

        method = getattr(self, 'cmd_' + pCommand.lower(), None)

        if method is None:
            self.PutModule('Invalid command {}'.format(pCommand))
            return znc.CONTINUE

        try:
            method(*args, **dict(list(kw)))
        except TypeError as e:
            self.PutModule('Usage: {}{}\n{}'.format(pCommand, signature(method), e))
            return znc.CONTINUE

        return znc.CONTINUE

    def cmd_help(self):
        '''Show this help'''
        cmds = [x[4:] for x in dir(self) if x.startswith('cmd_')]
        for cmd in cmds:
            self.PutModule('{}: {}'.format(cmd, getattr(self, 'cmd_'+cmd, None).__doc__))

    def cmd_backlog(self, chanOrNick, num=10, debug=False):
        '''Show backlog for channel'''
        c = self.logstore
        cols = (
                ("time","strftime('%Y-%m-%dT%H:%M:%fZ', \"time\")"),
                ("ftime", "datetime(\"time\", 'localtime')"),
                "who", "where", "type", "message")
        select_cols = ', '.join(('{1} as "{0}"'.format(*x) if isinstance(x,tuple) else '"{}"'.format(x)) for x in cols)
        col_names = [(x[0] if isinstance(x,tuple) else x) for x in cols]
        rows = c.execute(
            '''SELECT *
               FROM (
                SELECT {cols}
                FROM "log"
                WHERE lower("where")=lower(?)
                ORDER BY "time" DESC
                LIMIT ?)
               ORDER BY "time" ASC'''.format(cols=select_cols),
               (str(chanOrNick), int(num)))
        for row in rows:
            rowd = dict(zip(col_names, row))
            client = self.GetClient()
            isChanMsg = str(chanOrNick)[0] in ['#', '&', '!', '+']
            rowd['where'] = chanOrNick # case sensitivity hack
            if rowd['who'] is None:
                if client.HasSelfMessage() or isChanMsg:
                    rowd['who'] = self.GetNetwork().GetNick()
                else:
                    rowd['message'] = "<{who}>: {message}".format(**rowd)
                    rowd['who'] = chanOrNick
            if client.HasServerTime():
                timeattr = "@time={time} ".format(**rowd)
            else:
                timeattr = ""
                rowd['message'] = "[{ftime}] {message}".format(**rowd)
            if rowd['type'] is not None:
                rowd['message'] = '\x01{type} {message}\x01'.format(**rowd)
            self.PutUser("{}:{who}!znc@znc.in PRIVMSG {where} :{message}".format(timeattr, **rowd));

    def cmd_search(self, query, limit=10, debug=False):
        '''Search through history'''
        c = self.logstore
        cols = ["time", "who", "where", "type", "message"]
        # grammar definition
        def quoteStr(s,l,t):
            return ['"{}"'.format(*t)]
        def phfmt(s='?', fmt=None):
            return lambda t: (s, t[0] if fmt is None else fmt.format(*t))
        def Val(e, pa=phfmt()):
            return e.setParseAction(pa)

        column = MatchFirst(map(CaselessKeyword, cols[2:])).setParseAction(quoteStr) \
                | Val(CaselessKeyword("who"),replaceWith(('''COALESCE("who", ?)''', self.GetNetwork().GetNick())))
        number = Word(nums).setParseAction(lambda t: int(t[0]))
        word = Regex(r'\w+')
        operand = Val(number | sglQuotedString | word)
        binOpLit = oneOf('!= = > < >= <= <>') | CaselessKeyword('like')
        binOp = column + binOpLit + operand
        betweenLit = CaselessKeyword('between')
        andLit = CaselessKeyword('and')
        betweenOp = column + betweenLit + operand + andLit + operand
        tildeOp = column + Literal('~').setParseAction(replaceWith('like')) + Val( sglQuotedString | word, phfmt(fmt='%{}%'))
        comparison = binOp | betweenOp | tildeOp

        timecol = CaselessKeyword('time').setParseAction(replaceWith('''datetime("time", 'localtime')'''))
        time = Val(Regex(r'\d{2}:\d{2}(:\d{2})?'),phfmt('''datetime(date('now','localtime'), ?)'''))
        datetime = Val(Regex(r'\d{4}-\d{2}-d{2}(T|\s+)\d{2}:\d{2}:\d{2}'))
        nowLit = CaselessKeyword('now').setParseAction(replaceWith('''datetime('now', 'localtime')'''))
        timeop = time | datetime | nowLit

        datecol = CaselessKeyword('time').setParseAction(replaceWith('''date("time", 'localtime')'''))
        todayLit = CaselessKeyword('today').setParseAction(replaceWith('''date('now', 'localtime')'''))
        yesterdayLit = CaselessKeyword('yesterday').setParseAction(replaceWith('''date('now', 'localtime', '-1 day')'''))
        date = Val(Regex(r'\d{4}-\d{2}-\d{2}'))
        dateop = date | todayLit | yesterdayLit

        timecomp = timecol + binOpLit + timeop | timecol + betweenLit + timeop + andLit + timeop
        datecomp = datecol + binOpLit + dateop | datecol + betweenLit + dateop + andLit + dateop
        gquery = StringStart() + ZeroOrMore(Group(comparison | timecomp | datecomp)) + StringEnd()
        if query == 'help':
            self.PutModule(str(gquery))
            return
        try:
            parsed = gquery.parseString(query)
            vals = tuple(i[1] for cond in parsed for i in cond if isinstance(i, tuple))
            query_where = ' AND '.join(' '.join(i[0] if isinstance(i, tuple) else i for i in cond) for cond in parsed)
        except ParseException as e:
            self.PutModule('Invalid query: {}'.format(e))
            return
        if query_where == "":
            self.PutModule('Invalid query: {}'.format(query))
            return
        # end grammar definition
        query_sql ='''
            SELECT datetime("time", 'localtime') as "time", {cols}
            FROM "log"
            WHERE {qw}
            LIMIT ?
            '''.format(
                    cols=', '.join('"{}"'.format(x) for x in cols[1:]),
                    qw=query_where
                    )
        try:
            rows = c.execute(query_sql, vals+(limit,))
        except sqlite3.OperationalError as e:
            self.PutModule('Invalid query {}\n{}\n{}'.format(query_sql,vals,e))
            return
        except sqlite3.ProgrammingError as e:
            self.PutModule('Invalid query {}\n{}\n{}'.format(query_sql,vals,e))
            return
        if debug:
            self.PutModule('Debug: {}\n{}'.format(query_sql, vals))
        results = False
        for row in rows:
            results = True
            rowd = dict(zip(cols, row))
            if rowd['who'] is None:
                rowd['who'] = self.GetNetwork().GetNick()
            self.PutModule("{where} [{time}] <{who}>: {message}".format(**rowd));
        if not results:
            self.PutModule('No results')
