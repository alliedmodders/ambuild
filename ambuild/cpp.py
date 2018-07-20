# vim: set ts=2 sw=2 tw=99 noet:
from __future__ import print_function
import copy
import subprocess
import os
import sys
import ambuild.osutil as osutil
import re
import ambuild.command as command

class Vendor:
	def __init__(self, name, version, command, objSuffix):
		self.name = name
		self.version = version
		self.command = command
		self.objSuffix = objSuffix

	def AddIncludes(self, args, workPath, folders):
		for folder in folders:
			self.AddInclude(args, workPath, folder)

class MSVC(Vendor):
	def __init__(self, command, version):
		Vendor.__init__(self, 'msvc', version, command, '.obj')

	def AddInclude(self, args, workPath, folder):
		#Hack - try and get a relative path because CL, with either 
		#/Zi or /ZI, combined with subprocess, apparently tries and
		#looks for paths like c:\bleh\"c:\bleh" <-- wtf
		#.. this according to Process Monitor
		workPath = os.path.normcase(workPath)
		folder = os.path.normcase(folder)
		workdrive = os.path.splitdrive(workPath)[0]
		incdrive = os.path.splitdrive(folder)[0]
		if workdrive == incdrive:
			folder = os.path.relpath(folder, workPath)
		args.extend(['/I', folder])

class CompatGCC(Vendor):
	def __init__(self, name, command, version):
		Vendor.__init__(self, name, version, command, '.o')
		parts = version.split('.')
		self.majorVersion = int(parts[0])
		self.minorVersion = int(parts[1])

	def AddInclude(self, args, workPath, folder):
		args.extend(['-I', os.path.normpath(folder)])

class GCC(CompatGCC):
	def __init__(self, command, version):
		CompatGCC.__init__(self, 'gcc', command, version)

class Clang(CompatGCC):
	def __init__(self, command, version):
		CompatGCC.__init__(self, 'clang', command, version)

class Compiler:
	def __init__(self):
		self.env = { }
		self.env['CINCLUDES'] = []
		self.env['CXXINCLUDES'] = []
		self.env['POSTLINKFLAGS'] = []

	def Clone(self):
		c = Compiler()
		c.env = copy.deepcopy(self.env)
		c.cc = copy.deepcopy(self.cc)
		c.cxx = copy.deepcopy(self.cxx)
		return c

	def __getitem__(self, key):
		return self.env[key]

	def DetectAll(self, runner):
		osutil.PushFolder(os.path.join(runner.outputFolder, '.ambuild'))
		try:
			self.Setup()
			self.DetectCCompiler()
			self.DetectCxxCompiler()
			osutil.PopFolder()
		except Exception as e:
			osutil.PopFolder()
			raise e

	def ToConfig(self, runner, name):
		runner.cache.CacheVariable(name + '_env', self.env)
		runner.cache.CacheVariable(name + '_cc', self.cc)
		runner.cache.CacheVariable(name + '_cxx', self.cxx)

	def FromConfig(self, runner, name):
		env = runner.cache[name + '_env']
		self.env.update(env)
		self.cc = runner.cache[name + '_cc']
		self.cxx = runner.cache[name + '_cxx']

	def Setup(self):
		for var in ['CFLAGS', 'CPPFLAGS', 'CXXFLAGS']:
			self.ImportListVar(var)
		for var in ['CC', 'CXX']:
			self.ImportVar(var)

	def ImportListVar(self, key, sep = ' '):
		if not key in os.environ:
			return
		self.env[key] = os.environ[key].split(sep)

	def ImportVar(self, key):
		if not key in os.environ:
			return
		self.env[key] = os.environ[key]

	def AddToListVar(self, key, item):
		if type(item) == list:
			if not key in self.env:
				self.env[key] = item
			else:
				self.env[key].extend(item)
		else:
			if not key in self.env:
				self.env[key] = [item]
			else:
				self.env[key].append(item)

	def DetectCCompiler(self):
		if 'CC' in self.env:
			if self.TryVerifyCompiler(self.env['CC'], 'c'):
				return True
		else:
			list = ['gcc', 'clang', 'cc', 'icc']
			if osutil.IsMac():
				list = ['clang', 'gcc', 'cc', 'icc']
			elif osutil.IsWindows():
				list[0:0] = ['cl']
			for i in list:
				if self.TryVerifyCompiler(i, 'c'):
					return True
		raise Exception('Unable to find suitable C compiler')
		
	def DetectCxxCompiler(self):
		if 'CXX' in self.env:
			if self.TryVerifyCompiler(self.env['CXX'], 'cxx'):
				return True
		else:
			list = ['g++', 'clang++', 'c++', 'icc']
			if osutil.IsMac():
				list = ['clang++', 'g++', 'c++', 'icc']
			elif osutil.IsWindows():
				list[0:0] = ['cl']
			for i in list:
				if self.TryVerifyCompiler(i, 'cxx'):
					return True
		raise Exception('Unable to find suitable C++ compiler')

	def TryVerifyCompiler(self, name, mode):
		if osutil.IsWindows() and self.VerifyCompiler(name, mode, 'msvc'):
			return True
		return self.VerifyCompiler(name, mode, 'gcc')
				
	def VerifyCompiler(self, name, mode, vendor):
		args = name.split(' ')
		if 'CPPFLAGS' in self.env:
			args.extend(self.env['CPPFLAGS'])
		if 'CFLAGS' in self.env:
			args.extend(self.env['CFLAGS'])
		if mode == 'cxx' and 'CXXFLAGS' in self.env:
			args.extend(self.env['CXXFLAGS'])
		filename = 'test.{0}'.format(mode)
		file = open(filename, 'w')
		file.write("""
#include <stdio.h>
#include <stdlib.h>

int main()
{
#if defined __ICC
	printf("icc %d\\n", __ICC);
#elif defined __clang__
# if defined(__clang_major__) && defined(__clang_minor__)
	printf("clang %d.%d\\n", __clang_major__, __clang_minor__);
# else
	printf("clang 1.%d\\n", __GNUC_MINOR__);
# endif
#elif defined __GNUC__
	printf("gcc %d.%d\\n", __GNUC__, __GNUC_MINOR__);
#elif defined _MSC_VER
	printf("msvc %d\\n", _MSC_VER);
#elif defined __TenDRA__
	printf("tendra 0\\n");
#else
#error "Unrecognized compiler!"
#endif
#if defined __cplusplus
  printf("cxx\\n");
#else
	printf("c\\n");
#endif
	exit(0);
}
""")
		file.close()
		if mode == 'c':
			executable = 'test' + osutil.ExecutableSuffix()
		elif mode == 'cxx':
			executable = 'testp' + osutil.ExecutableSuffix()
		try:
			os.unlink(executable)
		except:
			pass
		if vendor == 'gcc' and mode == 'cxx':
			args.extend(['-fno-exceptions', '-fno-rtti'])
		args.extend([filename, '-o', executable])
		print('Checking {0} compiler (vendor test {1})... '.format(mode, vendor), end = '')
		print(args)
		p = osutil.CreateProcess(args)
		if p == None:
			print('not found')
			return False
		if osutil.WaitForProcess(p) != 0:
			print('failed with return code {0}'.format(p.returncode))
			return False
		exe = osutil.MakePath('.', executable)
		p = osutil.CreateProcess([executable], executable = exe)
		if p == None:
			print('failed to create executable')
			return False
		if osutil.WaitForProcess(p) != 0:
			print('executable failed with return code {0}'.format(p.returncode))
			return False
		lines = p.stdoutText.splitlines()
		if len(lines) != 2:
			print('invalid executable output')
			return False
		if lines[1] != mode:
			print('requested {0} compiler, found {1}'.format(mode, lines[1]))
		vendor, version = lines[0].split(' ')
		if vendor == 'gcc':
			v = GCC(name, version)
		elif vendor == 'clang':
			v = Clang(name, version)
		elif vendor == 'msvc':
			v = MSVC(name, version)
		else:
			print('Unknown vendor {0}'.format(vendor))
			return False
		if mode == 'c':
			self.cc = v
		elif mode == 'cxx':
			self.cxx = v
		print('found {0} version {1}'.format(vendor, version))
		return True

	def HasProp(self, item):
		return item in self.env

def ObjectFile(file):
	return re.sub('[^a-zA-Z0-9_]+', '_', os.path.splitext(file)[0])

class CompileCommand(command.Command):
	def __init__(self, runner, compiler, file, objFile, workFolder):
		command.Command.__init__(self)
		self.objFile = objFile
		fullFile = os.path.join(runner.sourceFolder, file)
		ext = os.path.splitext(fullFile)[1]

		if ext == '.c':
			info = compiler.cc
		else:
			info = compiler.cxx
			self.hadCxxFiles = True

		args = info.command.split(' ')

		if compiler.HasProp('CFLAGS'):
			args.extend(compiler['CFLAGS'])
		if compiler.HasProp('CDEFINES'):
			if isinstance(info, MSVC):
				args.extend(['/D' + define for define in compiler['CDEFINES']])
			else:
				args.extend(['-D' + define for define in compiler['CDEFINES']])
		if compiler.HasProp('CINCLUDES'):
			info.AddIncludes(args, workFolder, compiler['CINCLUDES'])

		if ext != '.c':
			if compiler.HasProp('CXXFLAGS'):
				args.extend(compiler['CXXFLAGS'])
			if compiler.HasProp('CXXINCLUDES'):
				info.AddIncludes(args, workFolder, compiler['CXXINCLUDES'])

		if isinstance(info, CompatGCC):
			args.extend(['-H', '-c', fullFile, '-o', objFile + info.objSuffix])
		elif isinstance(info, MSVC):
			args.extend(['/showIncludes', '/c', fullFile, '/Fo' + objFile + info.objSuffix])

		self.argv = args
		self.vendor = info

	def run(self, runner, job):
		p = command.RunDirectCommand(runner, self.argv)
		self.stdout = p.stdoutText
		self.stderr = p.stderrText

		if isinstance(self.vendor, CompatGCC):
			deps = self.ParseDepsGCC()
		elif isinstance(self.vendor, MSVC):
			deps = self.ParseDepsMSVC()

		if p.returncode != 0:
			raise Exception('terminated with non-zero return code {0}'.format(p.returncode))

		job.CacheVariable(self.objFile, deps)
	
	def ParseDepsGCC(self):
		newtext = ''
		lines = re.split('\n+', self.stderr)
		check = 0
		strip = False
		deps = []
		#Messy logic to get dependencies and strip output from stderr
		for i in lines:
			if check == 0:
				m = re.match('\.+\s+(.+)\s*$', i)
				if m == None:
					check = 1
				else:
					file = m.groups()[0]
					if FileExists(file):
						strip = True
						if file not in deps:
							deps.append(file)
					else:
						check = 1
			if check == 1:
				if i.startswith('Multiple include guards may be useful for:'):
					check = 2
					strip = True
				else:
					check = 0
					strip = False
			elif check == 2:
				if not i in deps:
					strip = False 
					check = 3
			if not strip and i != '':
					newtext += i + '\n'
		self.stderr = newtext
		return deps

	def ParseDepsMSVC(self):
		newtext = ''
		lines = re.split('\n+', self.stdout)
		deps = []
		for i in lines:
			m = re.match('Note: including file:\s+(.+)$', i)
			if m != None:
				file = m.groups()[0].strip()
				deps.append(file)
			elif i != '':
				newtext += i + '\n'
		self.stdout = newtext
		return deps

def FileExists(file):
	return osutil.FileExists(file)

def GetFileTime(file):
	return osutil.GetFileTime(file)

def IsFileNewer(this, that):
	return osutil.IsFileNewer(this, that)

class LinkCommand(command.DirectCommand):
	def __init__(self, args, binary, outfile):
		command.DirectCommand.__init__(self, args)
		self.binary = binary
		self.outfile = outfile

	def run(self, runner, job):
		if not self.binary.NeedsRelink(self.outfile):
			return
		command.DirectCommand.run(self, runner, job)

class BinaryBuilder:
	def __init__(self, binary, runner, job, compiler):
		self.sourceFiles = []
		self.objFiles = []
		self.binary = binary
		self.runner = runner
		self.compiler = compiler
		self.hadCxxFiles = False
		self.job = job
		self.mostRecentDepends = 0
		self.relinkQueue = []
		self.alwaysRelink = False
		self.RebuildIfNewer(runner.CallerScript(3))
		self.env = {'POSTLINKFLAGS': [], 'CXXINCLUDES': []}

	def __getitem__(self, key):
		return self.env[key]
	
	def AddObjectFiles(self, files):
		self.objFiles.extend(files)

	def AddSourceFiles(self, folder, files):
		for file in files:
			sourceFile = os.path.join(folder, file)
			self.AddSourceFile(sourceFile)

	def RebuildIfNewer(self, file):
		time = GetFileTime(file)
		if time > self.mostRecentDepends:
			self.mostRecentDepends = time

	def RelinkIfNewer(self, file):
		self.relinkQueue.append(file)

	def NeedsRelink(self, binaryPath):
		if self.alwaysRelink:
			return True

		if not FileExists(binaryPath):
			return True

		ourTime = GetFileTime(binaryPath)

		for i in self.objFiles:
			objFile = os.path.join(self.runner.outputFolder, self.job.workFolder, i)
			if not FileExists(objFile):
				return True
			if IsFileNewer(objFile, ourTime):
				return True

		for file in self.relinkQueue:
			if IsFileNewer(file, ourTime):
				return True

		return False

	def _SendToJob(self, type):
		self.job.AddCommandGroup(self.sourceFiles, False)
		if type == 'shared':
			binaryName = self.binary + osutil.SharedLibSuffix()
		elif type == 'executable':
			binaryName = self.binary + osutil.ExecutableSuffix()
		elif type == 'static':
			binaryName = osutil.StaticLibPrefix() + self.binary + osutil.StaticLibSuffix()
		binaryPath = os.path.join(self.runner.outputFolder, self.job.workFolder, binaryName)

		if len(self.sourceFiles) > 0:
			self.alwaysRelink = True

		if type == 'static':
			if osutil.IsUnixy():
				args = ['ar', 'rcs', binaryName]
				args.extend([i for i in self.objFiles])
				self.job.AddCommand(LinkCommand(args, self, binaryPath))
				return
			else:
				args = ['lib.exe', '/OUT:' + binaryName]
				args.extend([i for i in self.objFiles])
				self.job.AddCommand(LinkCommand(args, self, binaryPath))
				return

		if self.hadCxxFiles:
			cc = self.compiler.cxx
		else:
			cc = self.compiler.cc
		args = cc.command.split(' ')
		args.extend([i for i in self.objFiles])
		if isinstance(cc, MSVC):
			args.append('/link')
		args.extend(self.compiler['POSTLINKFLAGS'])
		args.extend(self.env['POSTLINKFLAGS'])
		if isinstance(cc, CompatGCC):
			if type == 'shared':
				if self.runner.target['platform'] == 'darwin':
					args.append('-dynamiclib')
				else:
					args.append('-shared')
			args.extend(['-o', binaryName])
		elif isinstance(cc, MSVC):
			args.append('/OUT:' + binaryName)
			if type == 'shared':
				args.append('/DLL')
			args.append('/PDB:"' + self.binary + '.pdb' + '"')
		self.job.AddCommand(LinkCommand(args, self, binaryPath))

	def AddResourceFile(self, file, env):
		if self.runner.target['platform'] != 'windows':
			return
		objFile = ObjectFile(file) + '.res'

		self.objFiles.append(objFile)

		objFilePath = os.path.join(self.runner.outputFolder, self.job.workFolder, objFile)
		fullFile = os.path.join(self.runner.sourceFolder, file)
		if FileExists(objFilePath) and IsFileNewer(objFilePath, fullFile) and \
		   GetFileTime(objFilePath) > self.mostRecentDepends:
			 #:TODO: we need to deduce RC dependencies
			 return

		args = ['rc']

		for e in [env, self.env, self.compiler.env]:
			if 'RCDEFINES' in e:
				for define in e['RCDEFINES']:
					args.extend(['/d', define])
			if 'RCINCLUDES' in e:
				for include in e['RCINCLUDES']:
					args.extend(['/i', include])
			
		args.extend(['/fo' + objFile, fullFile])
		self.sourceFiles.append(command.DirectCommand(args))

	def AddSourceFile(self, file):
		objFile = ObjectFile(file)
		ext = os.path.splitext(file)[1]

		if ext == '.c':
			suffix = self.compiler.cc.objSuffix
		else:
			suffix = self.compiler.cxx.objSuffix
		self.objFiles.append(objFile + suffix)

		objFilePath = os.path.join(self.runner.outputFolder, self.job.workFolder, objFile) + \
		              suffix
		fullFile = os.path.join(self.runner.sourceFolder, file)
		if FileExists(objFilePath) and IsFileNewer(objFilePath, fullFile) and \
		   GetFileTime(objFilePath) > self.mostRecentDepends:
			#compute full dependencies, this isn't enough.
			if self.job.HasVariable(objFile):
				list = self.job.GetVariable(objFile)
				checked = True
				for i in list:
					if not FileExists(i) or IsFileNewer(i, objFilePath):
						checked = False
						break
				#if all dependencies checked out, we're good to go.
				if checked == True:
					return

		workFolder = os.path.join(self.runner.outputFolder, self.job.workFolder)
		self.sourceFiles.append(CompileCommand(self.runner, self.compiler, file, objFile, workFolder))

class LibraryBuilder(BinaryBuilder):
	def __init__(self, binary, runner, job, compiler):
		BinaryBuilder.__init__(self, binary, runner, job, compiler)
		self.binaryFile = binary + osutil.SharedLibSuffix()
	
	def SendToJob(self):
		self._SendToJob('shared')

class ExecutableBuilder(BinaryBuilder):
	def __init__(self, binary, runner, job, compiler):
		BinaryBuilder.__init__(self, binary, runner, job, compiler)
		self.binaryFile = binary + osutil.ExecutableSuffix()
	
	def SendToJob(self):
		self._SendToJob('executable')

class StaticLibraryBuilder(BinaryBuilder):
	def __init__(self, binary, runner, job, compiler):
		BinaryBuilder.__init__(self, binary, runner, job, compiler)
		self.binaryFile = osutil.StaticLibPrefix() + binary + osutil.StaticLibSuffix()

	def SendToJob(self):
		self._SendToJob('static')


