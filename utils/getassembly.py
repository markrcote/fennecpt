#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2010 Hubert Hanghofer
# hubert.hanghofer.net
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

def getassembly(s):
    """
getassembly(str) --> String
returns the Assembly-String included in Microsoft .EXE or .DLL files
    """
    f = open(s, "rb")
    result = ""
    for line in f:
        if "<assembly" in line:
            t = line.partition("<assembly")
            result = t[1] + t[2]
            for line in f:
                if "</assembly>" in line:
                    t = line.partition("</assembly>")
                    result += (t[0] + t[1])
                    f.close()
                    return result
                else:
                    result += line
    f.close()
    return "No assembly found!"



if __name__ == "__main__":
    import sys
    from glob import glob
    
    if len(sys.argv) > 1:
        try:
            for f in glob(sys.argv[1]):
                print "fetching assembly from {file}:\n".format(file = f)
                print getassembly(f), '\n'
        except(IOError) as detail:
            print "Error:", detail
    else: print "please specify a DLL or EXE file"