# vim: set ts=2 sw=2 tw=99 noet:
import subprocess
import os
import sys
import ambuild.osutil as osutil
import re
import ambuild.command as command

class Compiler:
	def Clone(self):
		c = Compiler()
		c.env = { }
		for i in self.env:
			c.env[i] = self.env[i]
		c.cc = self.cc
		c.cxx = self.cxx
		return c

	def FromConfig(self, name, runner):
		self.env = { }
		if runner.mode == 'config':
			osutil.PushFolder(os.path.join(runner.outputFolder, '.ambuild'))
			try:
				self.Setup()
				self.DetectCCompiler()
				self.DetectCxxCompiler()
				osutil.PopFolder()
			except Exception as e:
				osutil.PopFolder()
				raise e
			runner.cache.CacheVariable(name + '_env', self.env)
			runner.cache.CacheVariable(name + '_cc', self.cc)
			runner.cache.CacheVariable(name + '_cxx', self.cxx)
		else:
			self.env = runner.cache[name + '_env']
			self.cc = runner.cache[name + '_cc']
			self.cxx = runner.cache[name + '_cxx']

	def Setup(self):
		for var in ['CFLAGS', 'CPPFLAGS', 'CXXFLAGS', 'LDFLAGS', 'EXEFLAGS']:
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
		args.extend([filename, '-o', executable])
		if 'EXEFLAGS' in self.env:
			args.extend(self.env['EXEFLAGS'])
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

class CompileCommand(command.Command):
	def __init__(self, compiler, sourceFile):
		command.Command.__init__(self)
		self.sourceFile = sourceFile
		self.compiler = compiler

	def run(self, master, job):
		root, ext = os.path.splitext(self.sourceFile)
		compiler = self.compiler
		if ext == '.c':
			info = compiler.cc
			args = [info['command']]
			if compiler.HasProp('CFLAGS'):
				args.extend(compiler['CFLAGS'])
		else:
			info = compiler.cxx
			args = [info['command']]
			if compiler.HasProp('CFLAGS'):
				args.extend(compiler['CFLAGS'])
			if compiler.HasProp('CXXFLAGS'):
				args.extend(compiler['CXXFLAGS'])
		root = root.replace('/', '_')
		root = root.replace('\\', '_')
		root = root + '.o'
		if info['vendor'] == 'icc' or info['vendor'] == 'gcc' or info['vendor'] == 'tendra':
			args.extend(['-c', self.sourceFile, '-o', root])
		elif info['vendor'] == 'msvc':
			args.extend(['/c', self.sourceFile, '/Fo' + root])
		print(' '.join(args))
		p = osutil.CreateProcess(args)
		if osutil.WaitForProcess(p) != 0:
			print(p.stdoutText)
			print(p.stderrText)
			raise Exception('compilation failed with return code: {0}'.format(p.returncode))

