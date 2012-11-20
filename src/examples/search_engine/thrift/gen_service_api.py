#!/usr/bin/env python

import sys
import glob
import os

obj = 'service_api'

# generate thrift binding for cpp
cmd1 = 'thrift --gen cpp ' + obj + '.thrift' + ' > /dev/null'
cmd2 = 'thrift --gen py ' + obj + '.thrift' + ' > /dev/null'
os.system(cmd1)
os.system(cmd2)

# change extension from cpp to cc
cppfile = glob.glob('./gen-cpp/*.cpp')
for filename in cppfile:
    ccfile = filename.replace('.cpp', '.cc')
    os.rename(filename, ccfile)
    #if ('skeleton' in ccfile):
    #    os.remove(ccfile)

# generate new SEBS file

# generate basic type lib
outfile = open("./gen-cpp/SEBS", 'w')
outfile.write("_cpp = sebs.import_(\"//sebs/cpp.sebs\")\n\n")
outfile.write(obj + '_lib = _cpp.Library(\n')
outfile.write('  name = \"' + obj + '_lib\",\n')
outfile.write('  srcs = [\"' + obj + '_constants.cc\",\n')
outfile.write('          \"' + obj + '_types.cc\"],\n')
outfile.write('  deps = [])\n\n')

# generate service lib
ccfile = glob.glob('./gen-cpp/*.cc')
for filename in ccfile:
    # AbcdEfgService -> abcd_efg_service
    if ('Service' in filename):
        name = filename.split('/')[-1].split('.')[0]
        upper_list = []
        for i in range(len(name)):
            if name[i].isupper():
                upper_list.append(i)
        str1 = ''
        for i in range(len(upper_list) - 1):
            str1 += name[upper_list[i]:upper_list[i + 1]].lower() + '_'
        str1 += name[upper_list[len(upper_list) - 1]:len(name)].lower()
        outfile.write(str1 + '_lib = _cpp.Library(\n')
        outfile.write('  name = \"' + str1 + '_lib\",\n')
        outfile.write('  srcs = [\"' + name + '.cc\",\n')
        outfile.write('         ],\n')
        outfile.write('  deps = [ ' + obj + '_lib,\n')
        outfile.write('         ])\n')

outfile.close()