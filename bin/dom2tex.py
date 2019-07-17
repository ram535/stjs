#!/usr/bin/env python

'''Convert HTML generated by Jekyll to LaTeX.'''

import sys
import io
import os
import argparse
import re
from bs4 import BeautifulSoup, NavigableString, Tag
from xml.dom.minidom import Node
from util import buildFilenames


CDATA_PAT = re.compile(r'<!\[CDATA\[(.+?)%\]\]>', re.DOTALL)


class Convert:
    def __init__(self):
        '''Setup.'''
        self.config = None
        self.output = None


    def run(self):
        '''Convert and fill in.'''
        self.config = self.parseArgs()
        fillings = self.convert()
        fillings.update({
            'title': self.config.title,
            'subtitle': self.config.subtitle,
            'author': self.config.author,
            'date': self.config.date
        })
        with open(self.config.template, 'r') as reader:
            template = reader.read()
        doc = template.format(**fillings)
        if self.config.output:
            with open(self.config.output, 'w') as writer:
                writer.write(doc)
        else:
            sys.stdout.write(doc)


    def parseArgs(self):
        '''Parse command-line arguments.'''
        parser = argparse.ArgumentParser()
        parser.add_argument('--title', type=str, help='title')
        parser.add_argument('--subtitle', type=str, help='subtitle')
        parser.add_argument('--author', type=str, help='author')
        parser.add_argument('--date', type=str, help='date')
        parser.add_argument('--links', type=str, help='file containing links table')
        parser.add_argument('--glossary', type=str, help='file containing glossary')
        parser.add_argument('--lessons', type=str, help='file containing lesson YAML')
        parser.add_argument('--standards', type=str, help='file containing standards YAML')
        parser.add_argument('--extras', type=str, help='file containing extras YAML')
        parser.add_argument('--template', type=str, help='LaTeX template')
        parser.add_argument('--output', type=str, help='Output file (default stdout)')
        parser.add_argument('--site', type=str, help='site directory')
        parser.add_argument('--verbose', action='store_true', help='report progress')
        parser.add_argument('files', type=str, nargs='*')
        return parser.parse_args()


    def convert(self):
        '''Convert all files.'''
        parts = buildFilenames(self.config)
        texts = {}
        for partName in parts:
            self.output = io.StringIO()
            for entry in parts[partName]:
                entry['dom'] = self.getDom(entry['htmlPath'])
                root = entry['dom'].find('main')
                self.recurse(entry, root)
            texts[partName] = self.output.getvalue()
        return texts


    def getDom(self, htmlPath):
        '''Get DOM from HTML file.'''
        path = os.path.join(self.config.site, htmlPath)
        text = open(path, 'r').read()
        dom = BeautifulSoup(text, 'lxml')
        return dom


    def recurse(self, entry, node):
        '''Recurse through DOM, generating LaTeX along the way.'''
        startName = f'{node.name}_start'
        if hasattr(self, startName):
            starter = getattr(self, startName)
            if not starter(entry, node):
                return
        else:
            self.error('UNKNOWN TAG', node.name, 'in', entry['slug'])
        for child in node.children:
            if isinstance(child, NavigableString):
                self.text(child.string)
            elif isinstance(child, Tag):
                self.recurse(entry, child)
            else:
                assert False, 'unsupported child type'
        endName = f'{node.name}_end'
        if hasattr(self, endName):
            ender = getattr(self, endName)
            ender(entry, node)


    def a_start(self, entry, node):
        if 'data-latex-text' in node.attrs:
            self.write(node.attrs['data-latex-text'])
            return False

        href = node.attrs['href']

        if href.startswith('http') or href.startswith('mailto'):
            self.write('\\href{', self.textEscape(href), '}{')
            return True

        if '#f:' in href:
            figId = href.split('#')[1]
            self.write('\\figref{', figId, '}')
            return False

        if '/glossary/' in href:
            key = href.split('#')[1]
            self.write('\\gref{', key, '}{')
            return True

        if href.startswith('#'):
            self.refSub(entry, href)
            return False

        if href.startswith('.') or href.startswith('/'):
            self.refCross(entry, href)
            return False

        self.error('UNKNOWN HREF', node.attrs['href'])
        return False


    def a_end(self, entry, node):
        self.write('}')


    def blockquote_start(self, entry, node):
        self.write('\\begin{quote}\n')
        return True


    def blockquote_end(self, entry, node):
        self.write('\\end{quote}\n')


    def code_start(self, entry, node):
        self.write('\\texttt{')
        return True


    def code_end(self, entry, node):
        self.write('}')


    def dd_start(self, entry, node):
        return True


    def dd_end(self, entry, node):
        pass


    def dl_start(self, entry, node):
        self.write('\\begin{itemize}\n')
        return True


    def dl_end(self, entry, node):
        self.write('\\end{itemize}\n')


    def dt_start(self, entry, node):
        if 'class' in node.attrs:
            if 'glossary' in node.attrs['class']:
                self.write('\\gitem{', node.attrs['id'], '}{')
                return True
        self.write('\\item[')
        return True


    def dt_end(self, entry, node):
        if 'class' in node.attrs:
            if 'glossary' in node.attrs['class']:
                self.write('}')
                return
        self.write(']')


    def div_start(self, entry, node):
        if 'summary' in node.attrs['class']:
            return True
        if 'author' in node.attrs['class']:
            return True
        if 'included-html' in node.attrs['class']:
            self.write('\\begin{minted}{html}\n')
            return True
        if 'highlighter-rouge' in node.attrs['class']:
            self.includeCode(entry, node)
            return False
        self.error('UNKNOWN DIV', entry['slug'], node)
        return True

    def div_end(self, entry, node):
        if 'included-html' in node.attrs['class']:
            self.write('\\end{minted}\n')


    def em_start(self, entry, node):
        self.write('\\emph{')
        return True

    def em_end(self, entry, node):
        self.write('}')


    def figcaption_start(self, entry, node):
        self.write('{')
        return True


    def figcaption_end(self, entry, node):
        self.write('}')


    def figure_start(self, entry, node):
        figId = node.attrs['id']
        img = node.find('img')
        src = self.imagePath(img.attrs['src'])
        title = img.attrs['title']
        figcaption = node.find('figcaption')
        self.write('\\figpdf{', src, '}{', figId, '}')
        self.recurse(entry, figcaption)
        return False


    def h1_start(self, entry, node):
        return self.headingStart(entry, node, 'chapter',
                                 entry['slug'])


    def h1_end(self, entry, node):
        self.headingEnd(entry, node, 'chapter',
                        entry['slug'])


    def h2_start(self, entry, node):
        if 'id' in node.attrs:
            return self.headingStart(entry, node, 'section',
                                     entry['slug'], node['id'])
        else:
            return self.headingStart(entry, node, 'section')


    def h2_end(self, entry, node):
        if 'id' in node.attrs:
            return self.headingEnd(entry, node, 'section',
                                   entry['slug'], node['id'])
        else:
            return self.headingEnd(entry, node, 'section')


    def h3_start(self, entry, node):
        if 'id' in node.attrs:
            return self.headingStart(entry, node, 'subsection',
                                     entry['slug'], node['id'])
        else:
            return self.headingStart(entry, node, 'subsection')


    def h3_end(self, entry, node):
        if 'id' in node.attrs:
            return self.headingEnd(entry, node, 'subsection',
                                   entry['slug'], node['id'])
        else:
            return self.headingEnd(entry, node, 'subsection')


    def img_start(self, entry, node):
        src = self.imagePath(node.attrs['src'])
        self.write('\\img{', src, '}')
        return False


    def li_start(self, entry, node):
        self.write('\\item ')
        return True


    def li_end(self, entry, node):
        self.write('\n')


    def main_start(self, entry, node):
        return True


    def main_end(self, entry, node):
        pass


    def ol_start(self, entry, node):
        self.write('\\begin{enumerate}')
        return True


    def ol_end(self, entry, node):
        self.write('\\end{enumerate}\n')


    def p_start(self, entry, node):
        self.write('\n')
        if 'class' in node.attrs:
            if 'lede' in node.attrs['class']:
                self.write('\\lede{')
            elif 'noindent' in node.attrs['class']:
                self.write('\\noindent\n')
            else:
                self.error('UNKNOWN PARAGRAPH', node.attrs['class'])
        return True


    def p_end(self, entry, node):
        if 'class' in node.attrs:
            if 'lede' in node.attrs['class']:
                self.write('}')
            elif 'noindent' in node.attrs['class']:
                pass
        self.write('\n')


    def script_start(self, entry, node):
        if 'math/tex' in node.attrs['type']:
            self.math(entry, node)
            return False
        self.error('UNKNOWN SCRIPT', node)
        return False


    def span_start(self, entry, node):
        if 'cite' in node.attrs['class']:
            self.citation(entry, node)
            return False
        self.error('UNKNOWN SPAN', node.attrs['class'])
        return True


    def strong_start(self, entry, node):
        self.write('\\textbf{')
        return True


    def strong_end(self, entry, node):
        self.write('}')


    def sup_start(self, entry, node):
        self.write('\\textsuperscript{')
        return True


    def sup_end(self, entry, node):
        self.write('}')


    def table_start(self, entry, node):
        alignment = self.tableGuessAlignment(node)
        self.write('\\begin{tabular}{', alignment, '}\n')
        for row in node.find_all('tr'):
            cells = self.tableGetCells(row)
            for (i, child) in enumerate(cells):
                self.recurse(entry, child)
                marker = ' \\\\\n' if (i == len(cells) - 1) else ' & '
                self.write(marker)
        self.write('\\end{tabular}')
        return False


    def td_start(self, entry, node):
        return True


    def th_start(self, entry, node):
        return True


    def ul_start(self, entry, node):
        self.write('\\begin{itemize}')
        return True


    def ul_end(self, entry, node):
        self.write('\\end{itemize}\n')


    def citation(self, entry, node):
        keys = ','.join([ref.attrs['href'].split('#')[1].strip()
                         for ref in node.find_all('a')])
        self.write('\\cite{', keys, '}')


    def refCross(self, entry, href):
        href = href.strip('./')
        if '#' in href:
            chapter, section = href.split('#')
            chapter = chapter.strip('/')
            self.write('\\secref{s:', chapter, ':', section, '}')
        else:
            self.write('\\chapref{s:', href, '}')


    def refSub(self, entry, href):
        section = href.lstrip('#')
        self.write('\\secref{s:', entry['slug'], ':', section, '}')


    def headingStart(self, entry, node, heading, *ids):
        if 'data-latex-heading' in node.attrs:
            heading = node.attrs['data-latex-heading']
        numbered = '' if ids else '*'
        self.write('\\', heading, numbered, '{')
        return True


    def headingEnd(self, entry, node, heading, *ids):
        self.write('}')
        if ids:
            self.write('\label{s:', ':'.join(ids), '}')


    def imagePath(self, path):
        if path.startswith('/'):
            path = '.' + path
        if path.endswith('.svg'):
            path = path.replace('.svg', '.pdf')
        return path


    def includeCode(self, entry, node):
        languages = [x for x in node.attrs['class'] if x.startswith('language')]
        if not languages:
            lang = 'text'
        else:
            lang = languages[0].split('-')[1]
        self.write('\\begin{minted}{', lang, '}\n')
        self.write(node.text.rstrip())
        self.write('\n', '\\end{minted}\n')


    def math(self, entry, node):
        match = CDATA_PAT.search(node.contents[0].string)
        if match:
            contained = match.group(1).strip()
            if contained.startswith('\\begin{align*}'):
                self.write(contained)
            else:
                self.write('$', contained, '$')
        else:
            self.write('$', node.text, '$')


    def tableGetCells(self, node):
        return [child for child in node.children
                if child.name in ('th', 'td')]


    def tableGuessAlignment(self, node):
        firstRow = node.find('tr')
        cells = self.tableGetCells(firstRow)
        return 'l' * len(cells)


    def text(self, node):
        assert isinstance(node, NavigableString), child
        text = self.textEscape(node.string)
        self.write(text)


    def textEscape(self, text):
        text = text.replace('\\', '{\\textbackslash}')
        for char in '_&#$%':
            text = text.replace(char, f'\\{char}')
        return text


    def write(self, *vals):
        for v in vals:
            self.output.write(v)


    def error(self, *args):
        print(*args, file=sys.stderr)


if __name__ == '__main__':
    convert = Convert()
    convert.run()
