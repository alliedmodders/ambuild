# vim: set ts=8 sts=4 sw=4 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.

from typing import Literal

from _typeshed import Incomplete
from ambuild2.frontend.system import System
from ambuild2.frontend.v2_2 import amb2_gen
from ambuild2.frontend.v2_2.context import BuildContext, RootBuildContext, TopLevelBuildContext
from ambuild2.frontend.v2_2.cpp.compiler import CliCompiler, Compiler
from ambuild2.frontend.v2_2.cpp.deptypes import CppNodes, PchNodes
from ambuild2.frontend.v2_2.cpp.gcc import GCC, Clang, Emscripten
from ambuild2.frontend.v2_2.cpp.msvc import MSVC
from ambuild2.frontend.v2_2.tools.fxc import FxcJob
from ambuild2.frontend.v2_2.tools.protoc import ProtocJob
from ambuild2.nodetypes import Entry, EnvDataTuple

type ModuleType = Module

def TargetSuffix(target: System) -> str: ...
def ComputeSourcePath(context: RootBuildContext | TopLevelBuildContext, localFolderNode: Entry, item: Entry | str) -> str: ...

class CustomSource:
    source: Entry
    weak_deps: list[Entry]
    def __init__(self, source: Entry, weak_deps: list[Entry] | None = None) -> None: ...

class CustomToolCommand:
    context: RootBuildContext | TopLevelBuildContext
    module_: Module
    localFolderNode: Entry
    data: FxcJob | ProtocJob
    sources: list[Entry]
    sourcedeps: list[Entry]
    def __init__(self, cx: RootBuildContext | TopLevelBuildContext, module: Module, localFolderNode: Entry, data: FxcJob | ProtocJob) -> None: ...
    @property
    def compiler(self) -> Compiler: ...
    @staticmethod
    def MakeLexicalFilename(path: str) -> str: ...
    def ComputeSourcePath(self, path: str) -> str: ...
    @staticmethod
    def CustomSource(source: Entry, weak_deps: list[Entry] | None = None) -> CustomSource: ...

class BuilderProxy:
    constructor_: type[Library | StaticLibrary | Program]
    sources: list[str]
    custom: list[Incomplete]
    compiler: CliCompiler
    include_hotlist: list[str]
    name_: str
    localFolder: str
    def __init__(self, builder: Project, compiler: CliCompiler, name: str) -> None: ...
    @property
    def outputFile(self) -> property: ...
    @property
    def type(self) -> property: ...

class Project:
    constructor_: type[Library | StaticLibrary | Program]
    name: str
    sources: list[str]
    include_hotlist: list[str]
    proxies_: list[BuilderProxy]
    builders_: list[Program | Library | StaticLibrary]
    custom: list[Incomplete]

    def __init__(self, constructor: type[Library | StaticLibrary | Program], name: str) -> None: ...
    def finish(self, cx: RootBuildContext | TopLevelBuildContext) -> None: ...
    def generate(self, generator: amb2_gen.Generator, cx: RootBuildContext | TopLevelBuildContext) -> list[CppNodes | PchNodes]: ...
    def Configure(self, compiler: CliCompiler, name: str, tag: str) -> BuilderProxy: ...

class ObjectFileTaskBase:
    env_data: EnvDataTuple
    folderNode: Entry
    inputObj: Entry
    sourcedeps: list[Entry]
    extra_inputs: list[Entry]
    outputs: list[str]
    dep_info: tuple[Literal['md'], str] | None

    def __init__(self, parent: ObjectArgvBuilder, inputObj: str, outputs: list[str]) -> None: ...
    @property
    def type(self) -> str: ...

class ObjectFileTask(ObjectFileTaskBase):
    argv: list[str]
    behavior: str

    def __init__(self, parent: ObjectArgvBuilder, inputObj: str, outputs: list[str], argv: list[str]) -> None: ...
    @property
    def type(self) -> Literal['object']: ...
    @property
    def object_file(self) -> str: ...

class RCFileTask(ObjectFileTaskBase):
    cl_argv: list[str]
    rc_argv: list[str]
    def __init__(self, parent: ObjectArgvBuilder, inputObj: str, outputs: list[str], cl_argv: list[str], rc_argv: list[str]) -> None: ...
    @property
    def type(self) -> Literal['resource']: ...
    @property
    def object_file(self) -> str: ...

class ObjectArgvBuilder:
    cx: BuildContext
    parent: Library | Program | StaticLibrary | PrecompiledHeaders
    outputPath: str | None
    localFolderNode: Entry | None
    vendor: GCC | Clang | Emscripten | MSVC | None
    compiler: CliCompiler | None
    cc_argv: list[str] | None
    cxx_argv: list[str] | None
    objects: list[ObjectFileTask | RCFileTask]
    resources: list[Incomplete]
    used_cxx: bool
    has_code: bool
    sourcedeps: list[Entry]
    env_data: EnvDataTuple | None
    extra_inputs: list[Entry]
    has_c_pch_: bool
    has_cxx_pch_: bool
    pch_nodes: list[PchNodes]
    has_shared_pdb: bool

    def __init__(self, cx: BuildContext, parent: Library | Program | StaticLibrary | PrecompiledHeaders) -> None: ...
    def setOutputs(self, localFolderNode: Entry, outputPath: str) -> None: ...
    def setCompiler(self, compiler: CliCompiler, addl_include_dirs: list[str], addl_source_deps: list[Entry]) -> None: ...
    def addPchDependency(self, pch: PchNodes) -> None: ...
    def buildItem(self, inputObj: str, sourceName: str, sourceFile: str) -> ObjectFileTask | RCFileTask: ...
    def buildCxxItem(self, inputObj: str, sourceFile: str, encodedName: str, extension: str) -> ObjectFileTask: ...
    def buildRcItem(self, inputObj: str, sourceFile: str, encodedName: str) -> ObjectFileTask | RCFileTask: ...
    def buildPchItem(self, input_obj: str, source_file: str) -> ObjectFileTask: ...
    def formatInclude(self, pch_list: list[str] | None, normal_list: list[str], include: str | PchNodes) -> None: ...

class Module:
    context: RootBuildContext | TopLevelBuildContext
    compiler: CliCompiler
    name: str
    sources: list[Entry | CustomSource]
    custom: list[FxcJob | ProtocJob]

    def __init__(self, context: RootBuildContext | TopLevelBuildContext, compiler: CliCompiler, name: str) -> None: ...

class BinaryBuilderBase:
    compiler: CliCompiler
    name_: str
    sources: list[str]
    localFolder: str

    def __init__(self, compiler: CliCompiler, name: str) -> None: ...
    def getBuildFolder(self, builder: RootBuildContext | TopLevelBuildContext) -> str: ...
    def computeModuleFolders(self, cx: RootBuildContext | TopLevelBuildContext, module_context: RootBuildContext | TopLevelBuildContext) -> tuple[str, str]: ...

class LinkerStep:
    base_name: str
    type: str
    argv: list[str]
    outputs: list[str]
    debug_entry: Entry | None
    shared_outputs: list[str]

    def __init__(self, base_name: str, type: str) -> None: ...

class BinaryBuilder(BinaryBuilderBase):
    custom: list[FxcJob | ProtocJob]
    include_hotlist: list[str]
    used_cxx_: bool
    linker_: GCC | Clang | Emscripten | MSVC
    modules_: list[ModuleType]
    has_code_: bool
    pch_nodes_: list[PchNodes]
    has_shared_pdb_: bool
    shared_cc_outputs: list[str]
    objects: list[ObjectFileTask | RCFileTask]
    linker_argv_: list[str]
    static_link_step: LinkerStep | None
    link_step: LinkerStep

    def __init__(self, compiler: CliCompiler, name: str) -> None: ...
    @property
    def outputFile(self) -> str: ...
    def generate(self, generator: amb2_gen.Generator, cx: RootBuildContext | TopLevelBuildContext) -> CppNodes: ...
    def Module(self, context: RootBuildContext | TopLevelBuildContext, name: str) -> ModuleType: ...
    @property
    def linker(self) -> GCC | Clang | Emscripten | MSVC: ...
    def linkFlags(self, cx: RootBuildContext | TopLevelBuildContext) -> list[str]: ...
    def buildModules(self, cx: RootBuildContext | TopLevelBuildContext) -> None: ...
    def buildModule(self, cx: RootBuildContext | TopLevelBuildContext, module: ModuleType) -> None: ...
    def finish(self, cx: RootBuildContext | TopLevelBuildContext) -> None: ...
    def computeLinkStep(self, cx: RootBuildContext | TopLevelBuildContext, files: list[str], name: str, link_type: Literal['program', 'library', 'static']) -> LinkerStep: ...
    def performSymbolSteps(self, cx: RootBuildContext | TopLevelBuildContext, step: LinkerStep) -> None: ...
    def computeLinkerOutputFile(self, name: str, link_type: Literal['program', 'library', 'static']) -> str: ...
    def computeLinkerArgv(self, cx: RootBuildContext | TopLevelBuildContext, files: list[str], name: str, link_type: Literal['program', 'library', 'static']) -> list[str]: ...
    def link(self, generator: amb2_gen.Generator, cx: RootBuildContext | TopLevelBuildContext, inputs: list[Entry]) -> CppNodes: ...
    def addLinkStep(self, context: RootBuildContext | TopLevelBuildContext, folder: Entry, inputs: list[Entry], step: LinkerStep) -> tuple[Entry, Entry | None]: ...

class Program(BinaryBuilder):
    compiler: CliCompiler
    name_: str
    sources: list[str]
    localFolder: str
    custom: list[FxcJob | ProtocJob]
    include_hotlist: list[str]

    def __init__(self, compiler: CliCompiler, name: str) -> None: ...
    @property
    def outputFile(self) -> str: ...
    @property
    def type(self) -> Literal['program']: ...

class Library(BinaryBuilder):
    compiler: CliCompiler
    name_: str
    sources: list[str]
    localFolder: str
    custom: list[FxcJob | ProtocJob]
    include_hotlist: list[str]

    def __init__(self, compiler: CliCompiler, name: str) -> None: ...
    @property
    def outputFile(self) -> str: ...
    @property
    def type(self) -> Literal['library']: ...

class StaticLibrary(BinaryBuilder):
    compiler: CliCompiler
    name_: str
    sources: list[str]
    localFolder: str
    custom: list[FxcJob | ProtocJob]
    include_hotlist: list[str]

    def __init__(self, compiler: CliCompiler, name: str) -> None: ...
    @property
    def outputFile(self) -> str: ...
    @property
    def type(self) -> Literal['static']: ...

class PrecompiledHeaders(BinaryBuilderBase):
    compiler: CliCompiler
    name_: str
    sources: list[str]
    localFolder: str
    source_type_: Literal['c', 'c++']

    def __init__(self, compiler: CliCompiler, name: str, source_type: str) -> None: ...
    @property
    def type(self) -> Literal['precompiled-headers']: ...
    @property
    def source_type(self) -> Literal['c', 'c++']: ...
    def finish(self, cx: RootBuildContext | TopLevelBuildContext) -> None: ...
    def generate(self, generator: amb2_gen.Generator, cx: RootBuildContext | TopLevelBuildContext) -> PchNodes: ...
