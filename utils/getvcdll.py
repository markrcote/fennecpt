#! /usr/bin/env python
from getassembly import getassembly
import os
import shutil
import xml.dom.minidom as dom

def main():
    import sys
    from glob import glob
    assembly = ''
    
    if len(sys.argv) > 1:
        try:
            for f in glob(sys.argv[1]):
                print "fetching assembly from {file}:\n".format(file = f)
                assembly = getassembly(f)
        except(IOError) as detail:
            print "Error:", detail
    else: print "please specify a DLL or EXE file"

    if not assembly:
        print 'Could not get assembly.'
        sys.exit(1)

    xml = dom.parseString(assembly)
    dep = xml.getElementsByTagName('dependentAssembly')[0]
    asid = dep.getElementsByTagName('assemblyIdentity')[0]
    components = dict(
      arch = asid.getAttribute('processorArchitecture'),
      name = asid.getAttribute('name'),
      tkn = asid.getAttribute('publicKeyToken'),
      ver = asid.getAttribute('version')
    )
    path = 'c:\\windows\\WinSxS\\%(arch)s_%(name)s_%(tkn)s_%(ver)s_x-ww_d08d0375' % components
    dll = 'msvcp90.dll'
    print 'Checking for %s in %s.' % (dll, path)
    if dll not in os.listdir(path):
        print 'Could not find DLL.'
        sys.exit(1)
    shutil.copyfile(os.path.join(path, dll), os.path.join(os.getcwd(), dll))
    print '%s copied into current directory.' % dll

if __name__ == '__main__':
    main()

