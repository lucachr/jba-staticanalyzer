import ast
import sys
import re
from abc import ABCMeta, abstractmethod
from pathlib import Path


class Analyzer(metaclass=ABCMeta):

    PATTERN_NOT_CAMEL_CASE = re.compile(r'[a-z0-9_]\w*')
    PATTERN_NOT_SNAKE_CASE = re.compile(r'[A-Z0-9]\w*')

    @property
    @abstractmethod
    def code(self):
        """Code of the check."""

    @property
    @abstractmethod
    def message(self):
        """Message of the check."""

    @classmethod
    @abstractmethod
    def check(cls, obj):
        """Check if a condition is true over obj.

        This method needs to be implemented in the derived classes.

        :param obj: Object checked.
        :returns: True if the condition checked is true, false
                  otherwise.
        """
        pass

    @classmethod
    def exec(cls, path, obj, lineno):
        """Execute the check defined inside the derived class.

        If the check returns True (i.e. there is something to fix),
        this function prints a help message for the user with details
        and result of the check.

        :param path: Path of the file checked.
        :param obj: Object checked.
        :param lineno: Number of the line checked.
        :returns: A dictionary containing line number, code and message
                  of the failed check.
        """
        if cls.check(obj):
            return {
                'lineno': lineno,
                'code': cls.code,
                'message': f'{path}: Line {lineno}: {cls.code} {cls.message}',
            }

    @classmethod
    @abstractmethod
    def execute_checks(cls, code, file):
        """Execute all the checks in a checker.

        :param code: Code of the file to check as a file object.
        :param file: Path of the file opened.
        :returns: A list of dictionaries that contains data of the
                  failed checks.
        """
        pass

    @classmethod
    def run(cls, file):
        """Run all the implemented check on a given file and print
        the results.

        :param file: Path of the file to check.
        """

        results = list()
        with open(file) as code:
            for checker in cls.__subclasses__():
                results.extend(checker.execute_checks(file, code))
                code.seek(0)

        for result in sorted(results, key=lambda r: (r['lineno'], r['code'])):
            print(result['message'])


class LineChecker(Analyzer, metaclass=ABCMeta):
    """Base class for checks on file lines."""

    @classmethod
    def execute_checks(cls, file, code):
        results = list()
        for i, line in enumerate(code, start=1):
            for check in cls.__subclasses__():
                if (result := check.exec(file, line, i)) is not None:
                    results.append(result)

        return results


class AstChecker(Analyzer, metaclass=ABCMeta):
    """Base class for checks on the abstract syntax tree of the file."""

    @classmethod
    def execute_checks(cls, file, code):
        results = list()
        tree = ast.parse(code.read())
        lineno = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.expr, ast.stmt)):
                lineno = node.lineno
            for check in cls.__subclasses__():
                if (result := check.exec(file, node, lineno)) is not None:
                    results.append(result)

        return results


class CheckTooLong(LineChecker):
    code = 'S001'
    message = 'Too long'

    @classmethod
    def check(cls, line):
        """Check if the line is over 79 characters long.

        :param line: Line of the file checked.
        :returns: True if the line is over 79 characters long, false
                  otherwise.
        """
        # Remove newline and spaces at the end before counting characters.
        return len(line.rstrip()) > 79


class CheckIndentationIsNotAMultipleOfFour(LineChecker):
    code = 'S002'
    message = 'Indentation is not a multiple of four'

    @classmethod
    def check(cls, line):
        """Check that the indentation is not a multiple of four spaces.

        :param line: Line of the file checked.
        :returns: True if the indentation is not a multiple of four,
                  false otherwise.
        """
        # Only spaces must be stripped to avoid issues with blank
        # lines (i.e. the newline is otherwise removed and an empty
        # obj seems incorrectly indented).
        spaces = len(line) - len(line.lstrip(' '))
        return spaces % 4 != 0


class CheckUnnecessarySemicolon(LineChecker):
    code = 'S003'
    message = 'Unnecessary semicolon'

    @classmethod
    def check(cls, line):
        """Check if there are unnecessary semicolons on the given obj.

        :param line: Line of the file checked.
        :returns: True if there are unnecessary semicolons, false otherwise.
        """
        single_quotes = False  # Are we inside quoted text?
        double_quotes = False
        for char in line:
            if char == '#':
                break
            if char == '"' and not single_quotes:  # Jump in and out of quotes
                double_quotes = not double_quotes
            if char == "'" and not double_quotes:  # Same as above
                single_quotes = not single_quotes
            if char == ';' and not (single_quotes or double_quotes):
                return True

        return False


class CheckLessThanTwoSpacesBeforeInlineComments(LineChecker):
    code = 'S004'
    message = 'At least two spaces required before inline comments'

    @classmethod
    def check(cls, line):
        """Check if less than two spaces are present before an inline
        comment.

        :param line: Line of the file checked.
        :returns: True if there are less than two spaces before an
                  inline comment, false otherwise.
        """
        return not line.startswith('#') and '#' in line and '  #' not in line


class CheckTodoFound(LineChecker):
    code = 'S005'
    message = 'TODO found'

    @classmethod
    def check(cls, line):
        """Check if there is a to-do comment on a given line.

        :param line: Line of the file checked.
        :returns: True if there is a to-do comment, false otherwise.
        """
        start = line.find('#')
        comment = line[start:]
        return 'todo' in comment.lower()


class CheckTooManyBlankLines(LineChecker):
    code = 'S006'
    message = 'Too many blank lines'
    blank_lines = 0

    @classmethod
    def check(cls, line):
        """Check if there are too many blank lines in the tested file.

        This method must be called on every line of a file for the
        check to be meaningful.

        :param line: Line of the file currently checked.
        :returns: True if there are too many blank lines, false
                  otherwise.
        """

        too_many_blanks = False

        if line.strip() == '':  # The obj is empty
            cls.blank_lines += 1
        else:
            if cls.blank_lines > 2:
                too_many_blanks = True
            cls.blank_lines = 0  # Reset count on lines with text.

        return too_many_blanks


class CheckTooManySpacesAfterConstructionName(LineChecker):
    code = 'S007'
    message = ''
    message_template = "Too many spaces after '{}'"
    pattern = re.compile(r' *(class|def)  +')

    @classmethod
    def check(cls, line):
        """Check if there are too many spaces after a constructor name.

        :param line: Line of the file currently checked.
        :returns: True if there are too many spaces after a constructor
                  name, false otherwise.
        """
        if (match := re.match(cls.pattern, line)) is not None:
            cls.message = cls.message_template.format(match.group(1))
            return True

        return False


class CheckClassNameShouldBeWrittenInCamelCase(AstChecker):
    code = 'S008'
    message = ''
    message_template = "Class name '{}' should use CamelCase"

    @classmethod
    def check(cls, node):
        """Check if class names are not written in CamelCase.

        :param node: Node of the file AST currently checked.
        :returns: True if there is a class name not written in
                  CamelCase on the checked line, false otherwise.
        """
        if isinstance(node, ast.ClassDef) and (
                re.match(cls.PATTERN_NOT_CAMEL_CASE, node.name) is not None):
            cls.message = cls.message_template.format(node.name)
            return True

        return False


class CheckFunctionNameShouldBeWrittenInSnakeCase(AstChecker):
    code = 'S009'
    message = ''
    message_template = "Function name '{}' should use snake_case"

    @classmethod
    def check(cls, node):
        """Check if function names are not written in snake_case.

        :param node: Node of the file AST currently checked.
        :returns: True if there is a function name not written in
                  snake_case on the checked line, false otherwise.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                re.match(cls.PATTERN_NOT_SNAKE_CASE, node.name) is not None):
            cls.message = cls.message_template.format(node.name)
            return True

        return False


class CheckArgumentNameShouldBeWrittenInSnakeCase(AstChecker):
    code = 'S010'
    message = ''
    message_template = "Argument name '{}' should be snake_case"

    @classmethod
    def check(cls, node):
        """Check if argument names are not written in snake_case.

        :param node: Node of the file AST currently checked.
        :returns: True if there is an argument name not written in
                  snake_case on the checked line, false otherwise.
        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                if re.match(cls.PATTERN_NOT_SNAKE_CASE, arg.arg) is not None:
                    cls.message = cls.message_template.format(arg.arg)
                    return True

        return False


class CheckVariableShouldBeWrittenInSnakeCase(AstChecker):
    code = 'S011'
    message = ''
    message_template = "Variable '{}' in function should be snake_case"

    @classmethod
    def check(cls, node):
        """Check if variable names are not written in snake_case.

        :param node: Node of the file AST currently checked.
        :returns: True if there is a variable name not written in
                  snake_case on the checked line, false otherwise.
        """
        target = None

        if isinstance(node, ast.Assign):
            target = node.targets[0]  # That's a simplification
        if isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            target = node.target

        if isinstance(target, ast.Name) and (
                re.match(cls.PATTERN_NOT_SNAKE_CASE, target.id) is not None):
            cls.message = cls.message_template.format(target.id)
            return True

        return False


class CheckDefaultArgumentValueIsMutable(AstChecker):
    code = 'S012'
    message = 'Default argument value is mutable'
    mutable = (ast.Dict, ast.List, ast.Set)

    @classmethod
    def check(cls, node):
        """Check if a default argument value is mutable.

        :param node: Node of the file AST currently checked.
        :returns: True if there is default argument value that is
                  mutable, false otherwise.
        """
        return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
            isinstance(arg, cls.mutable) for arg in node.args.defaults
        )


def main():
    # The first parameter is either a path to a file or a directory.
    path = Path(sys.argv[1])

    if path.is_file() and path.suffix == '.py':
        Analyzer.run(path)

    if path.is_dir():
        # Recursively execute checks on all the source code files.
        for file in sorted(path.glob('**/*.py')):
            Analyzer.run(file)


if __name__ == '__main__':
    main()
