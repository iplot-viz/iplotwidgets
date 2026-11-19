"""What a Python module of the processing offers, from its docstrings: the module, its submodules and their functions.
Only modules already loaded are described: describing one imports nothing, so runs none of its code."""

import html
import inspect
import re
import types
import typing

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QTextBrowser, QWidget

_BACK = 'back'
_FUNCTION = 'function:'


def modules_of(module: types.ModuleType, walk: bool) -> typing.List[types.ModuleType]:
    """The module and, if `walk`, the submodules that expressions reach through it, as the processing loads them: the
    loaded submodules that are attributes of it, and of those."""
    found = [module]
    if walk:
        for known in found:  # the list grows as it is walked
            for value in list(vars(known).values()):
                if inspect.ismodule(value) and value.__name__.startswith(known.__name__ + '.') and value not in found:
                    found.append(value)
    return found


def functions_of(module: types.ModuleType) -> typing.List[typing.Tuple[str, typing.Any]]:
    """The public functions and classes of a module, by name: those its __all__ names, or else those of its package
    (a module that imports others lists only its own)."""
    names = getattr(module, '__all__', None)
    root = module.__name__.split('.')[0]
    members = []
    for name in (vars(module) if names is None else names):
        value = getattr(module, name, None)
        if name.startswith('_') or not callable(value) or inspect.ismodule(value):
            continue
        if names is None and not str(getattr(value, '__module__', '') or '').startswith(root):
            continue
        members.append((name, value))
    return sorted(members, key=lambda member: member[0].lower())


_UNDERLINE = re.compile(r'\s*[=\-~^*#]{3,}\s*')  # under a title, in reStructuredText
_CALL = re.compile(r'[A-Za-z_][\w.]*(\(.*\))')


def paragraphs(doc: str) -> typing.List[str]:
    """The paragraphs of a docstring, each in one line, without the lines that underline titles."""
    blocks = ('\n'.join(line for line in block.splitlines() if not _UNDERLINE.fullmatch(line))
              for block in (doc or '').split('\n\n'))
    return [' '.join(block.split()) for block in blocks if block.strip()]


def signature_and_summary(value) -> typing.Tuple[str, str]:
    """How a function is called, and the first paragraph of its docstring. Functions written in C, as NumPy's, tell
    how they are called in the first paragraph instead."""
    doc = paragraphs(inspect.getdoc(value) or '')
    call = _CALL.fullmatch(doc[0]) if doc else None
    try:
        signature = str(inspect.signature(value))
    except (TypeError, ValueError):
        signature = call.group(1) if call else '(...)'
    if call:
        doc.pop(0)
    return signature, doc[0] if doc else ''


class ModuleDescription(QTextBrowser):
    """The page of a module: what it is, and its functions with how they are called and what they do. A function opens
    its whole docstring, with a way back."""

    def __init__(self, parent: typing.Optional[QWidget] = None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._open)
        self._title = ''
        self._modules: typing.List[types.ModuleType] = []
        self._index = ''
        self._pages: typing.Dict[tuple, str] = {}  # the pages shown, by title, module and walk
        self.describe('', None)

    def describe(self, title: str, module: typing.Optional[types.ModuleType], walk: bool = True):
        """Show the page of a loaded module, as `title` names it, or what to do without one."""
        self._title = title
        self._modules = [] if module is None else modules_of(module, walk)
        if module is None:
            text = f"{title} is not loaded." if title else "Select a module to read what it offers."
            self._index = f"<p><i>{html.escape(text)}</i></p>"
        elif (title, id(module), walk) in self._pages:
            self._index = self._pages[(title, id(module), walk)]
        else:
            # A page of a big package, as SciPy's, takes about a second the first time.
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._index = self._pages[(title, id(module), walk)] = self._index_page()
            finally:
                QGuiApplication.restoreOverrideCursor()
        self.setHtml(self._index)

    def _index_page(self) -> str:
        parts, listed = [f"<h2>{html.escape(self._title)}</h2>"], 0
        for module in self._modules:
            members = functions_of(module)
            if module is not self._modules[0]:
                if not members or module.__name__.rpartition('.')[2].startswith('_'):
                    continue  # nothing to offer, or private
                parts.append(f"<h3>{html.escape(module.__name__)}</h3>")
            parts += [f"<p>{html.escape(text)}</p>" for text in paragraphs(inspect.getdoc(module) or '')[:1]]
            for name, value in members:
                signature, summary = signature_and_summary(value)
                link = html.escape(f"{_FUNCTION}{module.__name__}:{name}", quote=True)
                parts.append(f"<p><a href=\"{link}\"><b>{html.escape(name)}</b></a>"
                             f"<code>{html.escape(signature)}</code>"
                             + (f"<br/>{html.escape(summary)}" if summary else "") + "</p>")
            listed += len(members)
        if not listed:
            parts.append("<p><i>It offers no functions.</i></p>")
        return ''.join(parts)

    def _open(self, url: QUrl):
        target = url.toString()
        if target == _BACK:
            self.setHtml(self._index)
            return
        module_name, _, name = target[len(_FUNCTION):].rpartition(':')
        module = next((module for module in self._modules if module.__name__ == module_name), None)
        value = getattr(module, name, None)
        if value is None:
            return
        signature, _ = signature_and_summary(value)
        doc = inspect.getdoc(value) or 'No documentation.'
        self.setHtml(f"<p><a href=\"{_BACK}\">&larr; {html.escape(self._title)}</a></p>"
                     f"<h3>{html.escape(module_name)}.{html.escape(name)}<code>{html.escape(signature)}</code></h3>"
                     f"<pre style=\"white-space: pre-wrap\">{html.escape(doc)}</pre>")
