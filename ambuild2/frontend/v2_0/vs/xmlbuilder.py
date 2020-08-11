# vim: set ts=8 sts=2 sw=2 tw=99 et:
#
# This file is part of AMBuild.
#
# AMBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# AMBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with AMBuild. If not, see <http://www.gnu.org/licenses/>.

class XmlScope(object):
    def __init__(self, builder, tag, **kwargs):
        self.builder_ = builder
        self.tag_ = tag
        self.kwargs_ = kwargs

    def __enter__(self):
        self.builder_.enter(self.tag_, **self.kwargs_)

    def __exit__(self, type, value, traceback):
        self.builder_.leave(self.tag_)

class XmlBuilder(object):
    def __init__(self, fp, version = "1.0", encoding = "utf-8"):
        super(XmlBuilder, self).__init__()
        self.fp_ = fp
        self.indent_ = 0
        self.write('<?xml version="{0}" encoding="{1}"?>'.format(version, encoding))

    def block(self, tag, **kwargs):
        return XmlScope(self, tag, **kwargs)

    def tag(self, tag, contents = None, **kwargs):
        open = self.build_element(tag, **kwargs)
        if contents is None:
            self.write('<{0} />'.format(open))
        else:
            self.write('<{0}>{1}</{2}>'.format(open, contents, tag))

    # Internal.
    def enter(self, tag, **kwargs):
        elt = self.build_element(tag, **kwargs)
        self.write('<{0}>'.format(elt))
        self.indent_ += 1

    def leave(self, tag):
        self.indent_ -= 1
        self.write('</{0}>'.format(tag))

    def build_element(self, tag, **kwargs):
        if len(kwargs) == 0:
            return '{0}'.format(tag)

        props = []
        for key in kwargs:
            props.append('{0}="{1}"'.format(key, kwargs[key]))
        attrs = ' '.join(props)
        return '{0} {1}'.format(tag, attrs)

    def write(self, line):
        self.fp_.write('  ' * self.indent_)
        self.fp_.write(line)
        self.fp_.write('\n')
