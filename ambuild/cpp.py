# vim: set ts=2 sw=2 tw=99 noet:
import copy
import subprocess
import os
import sys
import ambuild.osutil as osutil
import re
import ambuild.command as command

class Compiler:
	def __init__(self):
		self.env = { }
		self.env['CXXINCLUDES'] = []
		self.env['POSTLINKFLAGS'] = []

	def Clone(self):
		c = Compiler()
		c.env = copy.deepcopy(self.env)
		c.cc = self.cc
		c.cxx = self.cxx
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
		if not key in self.env:
			self.env[key] = [item]
		else:
			self.env[key].append(item)

	def DetectCCompiler(self):
		if 'CC' in self.env:
			if self.TryVerifyCompiler(self.env['CC'], 'c'):
				return True
		else:
			list = ['cc', 'icc']
			if osutil.IsWindows():
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
			list = ['g++', 'c++', 'icc'];
			if osutil.IsWindows():
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
		args = [name]
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
		if osutil.IsWindows():
			executable = 'test.exe'
		else:
			executable = 'test'
		try:
			os.unlink(executable)
		except:
			pass
		if vendor == 'gcc' and mode == 'cxx':
			args.extend(['-fno-exceptions', '-fno-rtti'])
		args.extend([filename, '-o', executable])
		print('Checking {0} compiler (vendor test {1})... '.format(mode, vendor), end = '')
		p = osutil.CreateProcess(args)
		if p == None:
			print('not found')
			return False
		if osutil.WaitForProcess(p) != 0:
			print('failed with return code {0}'.format(p.returncode))
			return False
		p = osutil.CreateProcess([executable], executable = osutil.MakePath('.', 'test'))
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
		if mode == 'c':
			self.cc = { 'vendor': vendor, 'version': version, 'command': name }
		elif mode == 'cxx':
			self.cxx = { 'vendor': vendor, 'version': version, 'command': name }
		print('found {0} version {1}'.format(vendor, version))
		return True

	def HasProp(self, item):
		return item in self.env

	def __getitem__(self, key):
		return self.env[key]

def ObjectFile(file):
	objFile = os.path.splitext(file)[0]
	objFile = objFile.replace('/', '_')
	objFile = objFile.replace('\\', '_')
	objFile = objFile.replace('.', '_')
	return objFile

class CompileCommand(command.Command):
	def __init__(self, runner, compiler, file, objFile):
		command.Command.__init__(self)
		self.objFile = objFile
		fullFile = os.path.join(runner.sourceFolder, file)
		ext = os.path.splitext(fullFile)[1]

		if ext == '.c':
			info = compiler.cc
		else:
			info = compiler.cxx
			self.hadCxxFiles = True

		args = [info['command']]

		if compiler.HasProp('CFLAGS'):
			args.extend(compiler['CFLAGS'])
		if compiler.HasProp('CDEFINES'):
			args.extend(['-D' + define for define in compiler['CDEFINES']])

		if ext != '.c':
			if compiler.HasProp('CXXFLAGS'):
				args.extend(compiler['CXXFLAGS'])
			if compiler.HasProp('CXXINCLUDES'):
				args.extend(['-I' + include for include in compiler['CXXINCLUDES']])

		if info['vendor'] == 'icc' or info['vendor'] == 'gcc':
			args.extend(['-H', '-c', fullFile, '-o', objFile + '.o'])

		self.argv = args
		self.vendor = info['vendor']

	def run(self, runner, job):
		p = command.RunDirectCommad(runner, self.argv)
		self.stdout = p.stdoutText
		self.stderr = p.stderrText
		if p.returncode != 0:
			raise Exception('terminated with non-zero return code {0}'.format(p.returncode))
		newtext = ''
		lines = re.split('\n+', self.stderr)
		check = 0
		deps = []
		#Messy logic to get GCC dependencies and strip output from stderr
		for i in lines:
			if check == 0:
				m = re.match('\.+\s+(.+)\s*$', i)
				if m == None:
					check = 1
				else:
					if os.path.isfile(m.groups()[0]):
						deps.append(m.groups()[0])
					else:
						check = 1
			if check == 1:
				if newtext.startswith('Multiple include guards may be useful for:'):
					check = 2
			elif check == 2:
				if not i in deps:
					newtext += i + '\n'
					check = 3
			elif check == 3:
					newtext += i + '\n'
		self.stderr = newtext
		#Phew! We have a list of dependencies, throw them into a cache file.
		job.CacheVariable(self.objFile, deps)

class LibraryBuilder:
	def __init__(self, binary, runner, job, compiler):
		self.sourceFiles = []
		self.objFiles = []
		self.binary = binary
		self.runner = runner
		self.compiler = compiler
		self.hadCxxFiles = False
		self.job = job
	
	def AddObjectFiles(self, files):
		self.objFiles.extend(files)

	def AddSourceFiles(self, folder, files):
		for file in files:
			sourceFile = os.path.join(folder, file)
			self.AddSourceFile(sourceFile)

	def NeedsRelink(self, binaryPath):
		if not os.path.isfile(binaryPath):
			return True
		for i in self.objFiles:
			objFile = os.path.join(self.runner.outputFolder, self.job.workFolder, i)
			if not os.path.isfile(objFile):
				return True
			if osutil.IsFileNewer(objFile, binaryPath):
				return True
		return False
			
	def SendToJob(self):
		self.job.AddCommandGroup(self.sourceFiles, False)
		binaryName = self.binary + osutil.SharedLibSuffix()
		binaryPath = os.path.join(self.runner.outputFolder, self.job.workFolder, binaryName)

		if len(self.sourceFiles) == 0 and not self.NeedsRelink(binaryPath):
			return

		if self.hadCxxFiles:
			cc = self.compiler.cxx
		else:
			cc = self.compiler.cc
		args = [cc['command']]
		args.extend([i for i in self.objFiles])
		args.extend(self.compiler['POSTLINKFLAGS'])
		if cc['vendor'] in ['gcc', 'icc', 'tendra']:
			args.extend(['-shared', '-o', binaryName])
		self.job.AddCommand(command.DirectCommand(args))

	def AddSourceFile(self, file):
		objFile = ObjectFile(file)
		self.objFiles.append(objFile + '.o')

		objFilePath = os.path.join(self.runner.outputFolder, self.job.workFolder, objFile) + '.o'
		fullFile = os.path.join(self.runner.sourceFolder, file)
		if os.path.isfile(objFilePath) and osutil.IsFileNewer(objFilePath, fullFile):
			#compute full dependencies, this isn't enough.
			if self.job.HasVariable(objFile):
				list = self.job.GetVariable(objFile)
				checked = True
				for i in list:
					if not os.path.isfile(i) or osutil.IsFileNewer(i, objFilePath):
						checked = False
						break
				#if all dependencies checked out, we're good to go.
				if checked == True:
					return

		self.sourceFiles.append(CompileCommand(self.runner, self.compiler, file, objFile))

