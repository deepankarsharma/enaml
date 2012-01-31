#------------------------------------------------------------------------------
#  Copyright (c) 2011, Enthought, Inc.
#  All rights reserved.
#------------------------------------------------------------------------------
import ast
import os

import ply.yacc as yacc

from . import enaml_ast
from .lexer import raise_syntax_error, EnamlLexer

from ..exceptions import EnamlSyntaxError


# Get a save directory for the lex and parse tables
_enaml_dir = os.path.join(os.path.expanduser('~'), '.enaml')
try:
    if not os.path.exists(_enaml_dir):
        os.mkdir(_enaml_dir)
except OSError:
    _enaml_dir = os.getcwd()


# Lexer tokens which need to be exposed to the parser
tokens = EnamlLexer.tokens


# The translation table for expression operators
operator_table = {
    '=': 'Equal',
    '<': 'Less',
    '>': 'Greater',
    ':': 'Colon',
}


# The allowed ast node types for ast.Store contexts
allowed_store = set([
    ast.Attribute,
    ast.Subscript,
    ast.Name,
    ast.List,
    ast.Tuple,
])


# The disallowed ast node types for ast.Store contexts and 
# the associated message tag for error reporting.
disallowed_store = {
    ast.Lambda: 'lambda',
    ast.Call: 'function call',
    ast.BoolOp: 'operator',
    ast.BinOp: 'operator',
    ast.UnaryOp: 'operator',
    ast.GeneratorExp: 'generator expression',
    ast.Yield: 'yield expression',
    ast.ListComp: 'list comprehension',
    ast.SetComp: 'set comprehension',
    ast.DictComp: 'dict comprehension',
    ast.Dict: 'literal',
    ast.Set: 'literal',
    ast.Num: 'literal',
    ast.Str: 'literal',
    ast.Ellipsis: 'Ellipsis',
    ast.Compare: 'comparison',
    ast.IfExp: 'conditional expression',
}


def translate_operator(op):
    """ Converts a symbolic operator into a string of the form
    __operator_<name>__ where <name> is result of translating the 
    symbolic operator using the operator_table.

    """
    op_table = operator_table
    name = ''.join(op_table[char] for char in op)
    return '__operator_%s__' % name


def raise_enaml_syntax_error(msg, lineno):
    """ Our own syntax error to punt on parsing since raising a regular
    SytaxError is special cased by ply.

    """
    msg = msg + ' - lineno (%s)' % lineno
    raise EnamlSyntaxError(msg)


def set_store_ctxt(node):
    """ Recursively sets the context of the node to ast.Store. If the
    node is not one of the allowed types for a store context, an error
    is raised with an appropriate message.

    """
    items = None
    err_msg = ''
    node_type = type(node)
    if node_type in allowed_store:
        node.ctx = ast.Store()
        if node_type == ast.Tuple:
            if len(node.elts) == 0:
                err_msg = '()'
            else:
                items = node.elts
        elif node_type == ast.List:
            items = node.elts
    elif node_type in disallowed_store:
        err_msg = disallowed_store[node_type]
    else:
        msg = 'unexpected expression in assignment %d (line %d)'
        raise SystemError(msg % (node_type.__name__, node.lineno))
    
    if err_msg:
        msg = "can't assign to %s" % err_msg
        raise EnamlSyntaxError(msg)
    
    if items is not None:
        for item in items:
            set_store_ctxt(item)


#------------------------------------------------------------------------------
# Enaml Module
#------------------------------------------------------------------------------
# These special rules to handle the variations of newline and endmarkers
# are because of the various lexer states that deal with python blocks
# and enaml code, as well as completely empty files.
def p_enaml1(p):
    ''' enaml : enaml_module NEWLINE ENDMARKER
              | enaml_module ENDMARKER '''
    p[0] = p[1]


def p_enaml2(p):
    ''' enaml : NEWLINE ENDMARKER
              | ENDMARKER '''
    p[0] = enaml_ast.Module('', [], -1)


def p_enaml3(p):
    ''' enaml : STRING NEWLINE ENDMARKER '''
    p[0] = enaml_ast.Module(p[1], [], -1)


def p_enaml_module1(p):
    ''' enaml_module : enaml_module_body '''
    p[0] = enaml_ast.Module('', p[1], -1)


def p_enaml_module2(p):
    ''' enaml_module : STRING NEWLINE enaml_module_body '''
    p[0] = enaml_ast.Module(p[1], p[3], -1)
    

#------------------------------------------------------------------------------
# Enaml Module Body
#------------------------------------------------------------------------------
def p_enaml_module_body1(p):
    ''' enaml_module_body : enaml_module_body enaml_module_item '''
    p[0] = p[1] + [p[2]]


def p_enaml_module_body2(p):
    ''' enaml_module_body : enaml_module_item '''
    p[0] = [p[1]]


#------------------------------------------------------------------------------
# Enaml Module Item
#------------------------------------------------------------------------------
def p_enaml_module_item1(p):
    ''' enaml_module_item : enaml_import '''
    p[0] = p[1]


def p_enaml_module_item2(p):
    ''' enaml_module_item : declaration '''
    p[0] = p[1]


def p_enaml_module_item3(p):
    ''' enaml_module_item : raw_python '''
    p[0] = p[1]


#------------------------------------------------------------------------------
# Raw Python
#------------------------------------------------------------------------------
def p_enaml_raw_python(p):
    ''' raw_python : PY_BLOCK_START NEWLINE PY_BLOCK PY_BLOCK_END NEWLINE '''
    # XXX update me to handle Python code without the start/end tags
    # Adding leading newlines before parsing so that any syntax errors
    # during parsing are reported with proper line numbers.
    py_txt = p[3]
    compile_txt = '\n' * p.lineno(1) + py_txt
    try:
        py_ast = ast.parse(compile_txt, p.lexer.filename, mode='exec')
    except SyntaxError as e:
        raise_syntax_error('invalid syntax', e.filename, e.lineno)
    p[0] = enaml_ast.Python(py_ast, p.lineno(1))


#------------------------------------------------------------------------------
# Enaml Import
#------------------------------------------------------------------------------
def p_enaml_import(p):
    ''' enaml_import : import_stmt '''
    imprt = p[1]
    mod = ast.Module(body=[imprt])
    p[0] = enaml_ast.Python(mod, imprt.lineno)


#------------------------------------------------------------------------------
# Declaration
#------------------------------------------------------------------------------
def p_declaration(p):
    ''' declaration : NAME LPAR NAME RPAR COLON declaration_body '''
    lineno = p.lineno(1)
    doc, idn, items = p[6]
    base = ast.Expression(body=ast.Name(id=p[3], ctx=ast.Load()))
    base.lineno = lineno
    ast.fix_missing_locations(base)
    base_node = enaml_ast.Python(base, lineno)
    p[0] = enaml_ast.Declaration(p[1], base_node, idn, doc, items, lineno)


def p_declaration_body1(p):
    ''' declaration_body : NEWLINE INDENT declaration_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[3])
    p[0] = ('', None, items)


def p_declaration_body2(p):
    ''' declaration_body : NEWLINE INDENT identifier DEDENT '''
    p[0] = ('', p[3], [])


def p_declaration_body3(p):
    ''' declaration_body : NEWLINE INDENT identifier declaration_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[4])
    p[0] = ('', p[3], items)


def p_declaration_body4(p):
    ''' declaration_body : NEWLINE INDENT STRING NEWLINE declaration_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[5])
    p[0] = (p[3], None, items)


def p_declaration_body5(p):
    ''' declaration_body : NEWLINE INDENT STRING NEWLINE identifier DEDENT '''
    p[0] = (p[3], p[5], [])


def p_declaration_body6(p):
    ''' declaration_body : NEWLINE INDENT STRING NEWLINE identifier declaration_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[6])
    p[0] = (p[3], p[5], items)


def p_declaration_body_items1(p):
    ''' declaration_body_items : declaration_body_item '''
    p[0] = [p[1]]


def p_declaration_body_items2(p):
    ''' declaration_body_items : declaration_body_items declaration_body_item '''
    p[0] = p[1] + [p[2]]


def p_declaration_body_item1(p):
    ''' declaration_body_item : attribute_declaration '''
    p[0] = p[1]


def p_declaration_body_item2(p):
    ''' declaration_body_item : attribute_binding '''
    p[0] = p[1]


def p_declaration_body_item3(p):
    ''' declaration_body_item : instantiation '''
    p[0] = p[1]


def p_declaration_body_item4(p):
    ''' declaration_body_item : PASS NEWLINE '''
    p[0] = None


#------------------------------------------------------------------------------
# Attribute Declaration
#------------------------------------------------------------------------------
def build_attr_declaration(kw, name, type_node, default, lineno, p):
    """ Builds an ast node for an attr or event declaration.

    Parameters
    ----------
    kw : string
        The keyword used in the declaration. A syntax error is raised if
        this is not 'attr' or 'event'.
    
    name : string
        The name of the attribute or event being declared.
    
    type_node : enaml_ast.Python node or None
        The expression node for the type being declared, or None if not 
        using a type.
    
    default : AttributeBinding or None
        The default attribute binding or None if not supply the default.

    lineno : int
        The line number of the declaration.
    
    p : Yacc Production
        The Ply object passed to the parser rule. This is used to 
        extract the filename for syntax error reporting.
    
    Returns
    -------
    result : AttributeDeclaration
        The Enaml AttributeDeclaration ast node.

    """
    if kw not in ('attr', 'event'):
        msg = "Expected keyword 'attr' or 'event', got '%s' instead." % kw
        raise_syntax_error(msg, p.lexer.filename, lineno)
    if kw == 'attr':
        res = enaml_ast.AttributeDeclaration(
            name, type_node, default, False, lineno,
        )
    else:
        res = enaml_ast.AttributeDeclaration(
            name, type_node, default, True, lineno,
        )
    return res


def p_attribute_declaration1(p):
    ''' attribute_declaration : NAME NAME NEWLINE '''
    p[0] = build_attr_declaration(p[1], p[2], None, None, p.lineno(1), p)


def p_attribute_declaration2(p):
    ''' attribute_declaration : NAME NAME COLON NAME NEWLINE '''
    lineno = p.lineno(1) 
    expr = ast.Expression(body=ast.Name(id=p[4], ctx=ast.Load()))
    expr.lineno = lineno
    ast.fix_missing_locations(expr)
    expr_node = enaml_ast.Python(expr, lineno)
    p[0] = build_attr_declaration(p[1], p[2], expr_node, None, p.lineno(1), p)


def p_attribute_declaration3(p):
    ''' attribute_declaration : NAME NAME binding '''
    lineno = p.lineno(1)
    name = p[2]
    binding = enaml_ast.AttributeBinding(name, p[3], lineno)
    p[0] = build_attr_declaration(p[1], name, None, binding, lineno, p)


def p_attribute_declaration4(p):
    ''' attribute_declaration : NAME NAME COLON NAME binding '''
    lineno = p.lineno(1)
    expr = ast.Expression(body=ast.Name(id=p[4], ctx=ast.Load()))
    expr.lineno = lineno
    ast.fix_missing_locations(expr)
    expr_node = enaml_ast.Python(expr, lineno)
    name = p[2]
    binding = enaml_ast.AttributeBinding(name, p[5], lineno)
    p[0] = build_attr_declaration(p[1], name, expr_node, binding, lineno, p)


#------------------------------------------------------------------------------
# Identifier
#------------------------------------------------------------------------------
def p_identifier(p):
    ''' identifier : NAME COLON NAME NEWLINE '''
    lhs = p[1]
    if lhs != 'id':
        msg = "'id' required. Got '%s' instead." % lhs
        raise_enaml_syntax_error(msg, p.lineno(1))
    p[0] = p[3]


#------------------------------------------------------------------------------
# Instantiation
#------------------------------------------------------------------------------
def p_instantiation(p):
    ''' instantiation : NAME COLON instantiation_body '''
    identifier, items = p[3]
    p[0] = enaml_ast.Instantiation(p[1], identifier, items, p.lineno(1))


def p_instantiation_body1(p):
    ''' instantiation_body : NEWLINE INDENT instantiation_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[3])
    p[0] = (None, items)


def p_instantiation_body2(p):
    ''' instantiation_body : NEWLINE INDENT identifier DEDENT '''
    p[0] = (p[3], [])


def p_instantiation_body3(p):
    ''' instantiation_body : NEWLINE INDENT identifier instantiation_body_items DEDENT '''
    # Filter out any pass statements
    items = filter(None, p[4])
    p[0] = (p[3], items)


def p_instantiation_body_items1(p):
    ''' instantiation_body_items : instantiation_body_item '''
    p[0] = [p[1]]


def p_instantiation_body_items2(p):
    ''' instantiation_body_items : instantiation_body_items instantiation_body_item '''
    p[0] = p[1] + [p[2]]


def p_instantiation_body_item1(p):
    ''' instantiation_body_item : instantiation '''
    p[0] = p[1]


def p_instantiation_body_item2(p):
    ''' instantiation_body_item : attribute_binding '''
    p[0] = p[1]


def p_instantiation_body_item3(p):
    ''' instantiation_body_item : PASS NEWLINE '''
    p[0] = None


#------------------------------------------------------------------------------
# Attribute Binding
#------------------------------------------------------------------------------
def p_attribute_binding(p):
    ''' attribute_binding : NAME binding '''
    p[0] = enaml_ast.AttributeBinding(p[1], p[2], p.lineno(1))


def p_binding1(p):
    ''' binding : EQUAL test NEWLINE
                | COLONEQUAL test NEWLINE
                | LEFTSHIFT test NEWLINE
                | RIGHTSHIFT test NEWLINE '''
    lineno = p.lineno(1) 
    operator = translate_operator(p[1])
    expr = ast.Expression(body=p[2])
    expr.lineno = lineno
    ast.fix_missing_locations(expr)
    expr_node = enaml_ast.Python(expr, lineno)
    p[0] = enaml_ast.BoundExpression(operator, expr_node, lineno)


def p_binding2(p):
    ''' binding : DOUBLECOLON simple_stmt_line '''
    lineno = p.lineno(1)
    operator = translate_operator(p[1])
    mod = ast.Module()
    mod.body = [p[2]]
    expr_node = enaml_ast.Python(mod, lineno)
    p[0] = enaml_ast.BoundExpression(operator, expr_node, lineno)


def p_binding3(p):
    ''' binding : DOUBLECOLON simple_stmt_suite '''
    lineno = p.lineno(1)
    operator = translate_operator(p[1])
    mod = ast.Module()
    mod.body = p[2]
    expr_node = enaml_ast.Python(mod, lineno)
    p[0] = enaml_ast.BoundExpression(operator, expr_node, lineno)


def p_simple_stmt_suite(p):
    ''' simple_stmt_suite : NEWLINE INDENT simple_stmt_list DEDENT '''
    p[0] = p[3]


def p_simple_stmt_list1(p):
    ''' simple_stmt_list : simple_stmt_line simple_stmt_list '''
    p[0] = [p[1]] + p[2]


def p_simple_stmt_list2(p):
    ''' simple_stmt_list : simple_stmt_line '''
    p[0] = [p[1]]


def p_simple_stmt_line(p):
    ''' simple_stmt_line : simple_stmt NEWLINE '''
    stmt = p[1]
    stmt.lineno = p.lineno(1)
    ast.fix_missing_locations(stmt)
    p[0] = stmt


#==============================================================================
# Begin Python Grammar
#==============================================================================

#------------------------------------------------------------------------------
# Statement Grammar
#------------------------------------------------------------------------------
def p_simple_stmt(p):
    ''' simple_stmt : small_stmt '''
    p[0] = p[1]


def p_small_stmt1(p):
    ''' small_stmt : expr_stmt '''
    p[0] = p[1]


def p_small_stmt2(p):
    ''' small_stmt : print_stmt '''
    p[0] = p[1]


def p_print_stmt1(p):
    ''' print_stmt : PRINT '''
    prnt = ast.Print()
    prnt.dest = None
    prnt.values = []
    prnt.nl = True
    p[0] = prnt


def p_print_stmt2(p):
    ''' print_stmt : PRINT testlist '''
    prnt = ast.Print()
    prnt.dest = None
    prnt.values = p[2]
    prnt.nl = True
    p[0] = prnt


def p_expr_stmt1(p):
    ''' expr_stmt : testlist '''
    rhs = p[1]
    if len(rhs) > 1:
        value = ast.Tuple()
        value.elts = rhs
        value.ctx = ast.Load()
    else:
        value = rhs[0]
        value.ctx = ast.Load()
    expr = ast.Expr()
    expr.value = value
    p[0] = expr


def p_expr_stmt2(p):
    ''' expr_stmt : testlist EQUAL testlist '''
    lineno = p.lineno(2)
    lhs = p[1]
    rhs = p[3]
    for item in lhs:
        set_store_ctxt(item)
    if len(rhs) > 1:
        value = ast.Tuple()
        value.elts = rhs
        value.ctx = ast.Load()
    else:
        value = rhs[0]
        value.ctx = ast.Load()
    assg = ast.Assign()
    assg.targets = lhs
    assg.value = value
    assg.lineno = lineno
    ast.fix_missing_locations(assg)
    p[0] = assg


def p_testlist1(p):
    ''' testlist : test '''
    p[0] = [p[1]]


def p_testlist2(p):
    ''' testlist : test COMMA '''
    p[0] = [p[1]]


def p_testlist3(p):
    ''' testlist : test testlist_list '''
    p[0] = [p[1]] + p[2]


def p_testlist4(p):
    ''' testlist : test testlist_list COMMA '''
    p[0] = [p[1]] + p[2]


def p_testlist_list1(p):
    ''' testlist_list : COMMA test '''
    p[0] = [p[2]]


def p_testlist_list2(p):
    ''' testlist_list : testlist_list COMMA test '''
    p[0] = p[1] + [p[3]]


#------------------------------------------------------------------------------
# Python Parsing Helper Objects
#------------------------------------------------------------------------------
class CommaSeparatedList(object):

    def __init__(self, values=None):
        self.values = values or []


class GeneratorInfo(object):

    def __init__(self, elt=None, generators=None):
        self.elt = elt
        self.generators = generators or []


class Arguments(object):

    def __init__(self, args=None, keywords=None, starargs=None, kwargs=None):
        self.args = args or []
        self.keywords = keywords or []
        self.starargs = starargs
        self.kwargs = kwargs


#------------------------------------------------------------------------------
# Import Grammar
#------------------------------------------------------------------------------
def p_import_stmt1(p):
    ''' import_stmt : import_name NEWLINE '''
    imprt = p[1]
    imprt.lineno = p.lineno(2)
    ast.fix_missing_locations(imprt)
    p[0] = imprt

    
def p_import_stmt2(p):
    ''' import_stmt : import_from NEWLINE '''
    imprt = p[1]
    imprt.lineno = p.lineno(2)
    ast.fix_missing_locations(imprt)
    p[0] = imprt


def p_import_name(p):
    ''' import_name : IMPORT dotted_as_names '''
    imprt = ast.Import(names=p[2])
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from1(p):
    ''' import_from : FROM dotted_name IMPORT STAR '''
    alias = ast.alias(name=p[4], asname=None)
    imprt = ast.ImportFrom(module=p[2], names=[alias], level=0)
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from2(p):
    ''' import_from : FROM dotted_name IMPORT import_as_names '''
    imprt = ast.ImportFrom(module=p[2], names=p[4], level=0)
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from3(p):
    ''' import_from : FROM dotted_name IMPORT LPAR import_as_names RPAR '''
    imprt = ast.ImportFrom(module=p[2], names=p[5], level=0)
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from4(p):
    ''' import_from : FROM import_from_dots dotted_name IMPORT STAR '''
    alias = ast.alias(name=p[5], asname=None)
    imprt = ast.ImportFrom(module=p[3], names=[alias], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from5(p):
    ''' import_from : FROM import_from_dots dotted_name IMPORT import_as_name '''
    imprt = ast.ImportFrom(module=p[3], names=p[5], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from6(p):
    ''' import_from : FROM import_from_dots dotted_name IMPORT LPAR import_as_names RPAR '''
    imprt = ast.ImportFrom(module=p[3], names=p[6], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from7(p):
    ''' import_from : FROM import_from_dots IMPORT STAR '''
    alias = ast.alias(name=p[4], asname=None)
    imprt = ast.ImportFrom(module=None, names=[alias], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from8(p):
    ''' import_from : FROM import_from_dots IMPORT import_as_names '''
    imprt = ast.ImportFrom(module=None, names=p[4], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from9(p):
    ''' import_from : FROM import_from_dots IMPORT LPAR import_as_names RPAR '''
    imprt = ast.ImportFrom(module=None, names=p[5], level=len(p[2]))
    imprt.col_offset = 0
    p[0] = imprt


def p_import_from_dots1(p):
    ''' import_from_dots : DOT '''
    p[0] = [p[1]]


def p_import_from_dots2(p):
    ''' import_from_dots : import_from_dots DOT '''
    p[0] = p[1] + [p[2]]


def p_import_as_name1(p):
    ''' import_as_name : NAME '''
    p[0] = ast.alias(name=p[1], asname=None)


def p_import_as_name2(p):
    ''' import_as_name : NAME AS NAME '''
    p[0] = ast.alias(name=p[1], asname=p[3])


def p_dotted_as_name1(p):
    ''' dotted_as_name : dotted_name '''
    alias = ast.alias(name=p[1], asname=None)
    p[0] = alias


def p_dotted_as_name2(p):
    ''' dotted_as_name : dotted_name AS NAME '''
    alias = ast.alias(name=p[1], asname=p[3])
    p[0] = alias


def p_import_as_names1(p):
    ''' import_as_names : import_as_name '''
    p[0] = [p[1]]


def p_import_as_names2(p):
    ''' import_as_names : import_as_name COMMA '''
    p[0] = [p[1]]


def p_import_as_names3(p):
    ''' import_as_names : import_as_name import_as_names_list '''
    p[0] = [p[1]] + p[2]


def p_import_as_names4(p):
    ''' import_as_names : import_as_name import_as_names_list COMMA '''
    p[0] = [p[1]] + p[2]


def p_import_as_names_list1(p):
    ''' import_as_names_list : COMMA import_as_name '''
    p[0] = [p[2]]


def p_import_as_names_list2(p):
    ''' import_as_names_list : import_as_names_list COMMA import_as_name '''
    p[0] = p[1] + [p[3]]


def p_dotted_as_names1(p):
    ''' dotted_as_names : dotted_as_name '''
    p[0] = [p[1]]


def p_dotted_as_names2(p):
    ''' dotted_as_names : dotted_as_name dotted_as_names_list '''
    p[0] = [p[1]] + p[2]


def p_dotted_as_names_list1(p):
    ''' dotted_as_names_list : COMMA dotted_as_name '''
    p[0] = [p[2]]


def p_dotted_as_names_star_list2(p):
    ''' dotted_as_names_list : dotted_as_names_list COMMA dotted_as_name '''
    p[0] = p[1] + [p[3]]


def p_dotted_name1(p):
    ''' dotted_name : NAME '''
    p[0] = p[1]


def p_dotted_name2(p):
    ''' dotted_name : NAME dotted_name_list '''
    p[0] = p[1] + p[2]


def p_dotted_name_list1(p):
    ''' dotted_name_list : DOT NAME '''
    p[0] = p[1] + p[2]


def p_dotted_name_list2(p):
    ''' dotted_name_list : dotted_name_list DOT NAME '''
    p[0] = p[1] + p[2] + p[3]


#------------------------------------------------------------------------------
# Expression Grammar   ('test' is the generic python expression)
#------------------------------------------------------------------------------
def p_test1(p):
    ''' test : or_test '''
    p[0] = p[1]


def p_test2(p):
    ''' test : or_test IF or_test ELSE test '''
    ifexp = ast.IfExp(body=p[1], test=p[3], orelse=p[5])
    p[0] = ifexp


def p_test3(p):
    ''' test : lambdef '''
    p[0] = p[1]


def p_or_test1(p):
    ''' or_test : and_test '''
    p[0] = p[1]


def p_or_test2(p):
    ''' or_test : and_test or_test_list '''
    values = [p[1]] + p[2]
    or_node = ast.BoolOp(op=ast.Or(), values=values)
    p[0] = or_node


def p_or_test_list1(p):
    ''' or_test_list : OR and_test '''
    p[0] = [p[2]]


def p_or_test_list2(p):
    ''' or_test_list : or_test_list OR and_test '''
    p[0] = p[1] + [p[3]]


def p_and_test1(p):
    ''' and_test : not_test '''
    p[0] = p[1]


def p_and_test2(p):
    ''' and_test : not_test and_test_list '''
    values = [p[1]] + p[2]
    and_node = ast.BoolOp(op=ast.And(), values=values)
    p[0] = and_node


def p_and_test_list1(p):
    ''' and_test_list : AND not_test '''
    p[0] = [p[2]]


def p_and_test_list2(p):
    ''' and_test_list : and_test_list AND not_test '''
    p[0] = p[1] + [p[3]]


def p_not_test(p):
    ''' not_test : comparison '''
    p[0] = p[1]


def p_not_test2(p):
    ''' not_test : NOT not_test '''
    un_node = ast.UnaryOp(op=ast.Not(), operand=p[2])
    p[0] = un_node


def p_comparison1(p):
    ''' comparison : expr '''
    p[0] = p[1]


def p_comparison2(p):
    ''' comparison : expr comparison_list '''
    left = p[1]
    ops, comparators = zip(*p[2])
    cmpr = ast.Compare(left=left, ops=list(ops), comparators=list(comparators))
    p[0] = cmpr


def p_comparison_list1(p):
    ''' comparison_list : comp_op expr '''
    p[0] = [[p[1], p[2]]]


def p_comparison_list2(p):
    ''' comparison_list : comparison_list comp_op expr '''
    p[0] = p[1] + [[p[2], p[3]]]


def p_comp_op1(p):
    ''' comp_op : LESS ''' 
    p[0] = ast.Lt()


def p_comp_op2(p):
    ''' comp_op : GREATER ''' 
    p[0] = ast.Gt()


def p_comp_op3(p):
    ''' comp_op : EQEQUAL ''' 
    p[0] = ast.Eq()


def p_comp_op4(p):
    ''' comp_op : GREATEREQUAL ''' 
    p[0] = ast.GtE()


def p_comp_op5(p):
    ''' comp_op : LESSEQUAL ''' 
    p[0] = ast.LtE()


def p_comp_op6(p):
    ''' comp_op : NOTEQUAL ''' 
    p[0] = ast.NotEq()


def p_comp_op7(p):
    ''' comp_op : IN ''' 
    p[0] = ast.In()


def p_comp_op8(p):
    ''' comp_op : NOT IN ''' 
    p[0] = ast.NotIn()


def p_comp_op9(p):
    ''' comp_op : IS ''' 
    p[0] = ast.Is()


def p_comp_op10(p):
    ''' comp_op : IS NOT ''' 
    p[0] = ast.IsNot()


def p_expr1(p):
    ''' expr : xor_expr '''
    p[0] = p[1]


def p_expr2(p):
    ''' expr : xor_expr expr_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node


def p_expr_list1(p):
    ''' expr_list : VBAR xor_expr '''
    p[0] = [[ast.BitOr(), p[2]]]


def p_expr_list2(p):
    ''' expr_list : expr_list VBAR xor_expr '''
    p[0] = p[1] + [[ast.BitOr(), p[3]]]


def p_xor_expr1(p):
    ''' xor_expr : and_expr '''
    p[0] = p[1]


def p_xor_expr2(p):
    ''' xor_expr : and_expr xor_expr_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node
    

def p_xor_expr_list1(p):
    ''' xor_expr_list : CIRCUMFLEX and_expr '''
    p[0] = [[ast.BitXor(), p[1]]]


def p_xor_expr_list2(p):
    ''' xor_expr_list : xor_expr_list CIRCUMFLEX and_expr '''
    p[0] = p[1] + [[ast.BitXor(), p[3]]]


def p_and_expr1(p):
    ''' and_expr : shift_expr '''
    p[0] = p[1]


def p_and_expr2(p):
    ''' and_expr : shift_expr and_expr_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node


def p_and_expr_list1(p):
    ''' and_expr_list : AMPER shift_expr '''
    p[0] = [[ast.BitAnd(), p[3]]]


def p_and_expr_list2(p):
    ''' and_expr_list : and_expr_list AMPER shift_expr '''
    p[0] = p[1] + [[ast.BitAnd(), p[3]]]


def p_shift_expr1(p):
    ''' shift_expr : arith_expr '''
    p[0] = p[1]


def p_shift_expr2(p):
    ''' shift_expr : arith_expr shift_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node


def p_shift_list1(p):
    ''' shift_list : shift_op '''
    p[0] = [p[1]]


def p_shift_list2(p):
    ''' shift_list : shift_list shift_op '''
    p[0] = p[1] + [p[2]]


def p_shift_op1(p):
    ''' shift_op : LEFTSHIFT arith_expr '''
    p[0] = [ast.LShift(), p[2]]


def p_shift_op2(p):
    ''' shift_op : RIGHTSHIFT arith_expr '''
    p[0] = [ast.RShift(), p[2]]


def p_arith_expr1(p):
    ''' arith_expr : term '''
    p[0] = p[1]


def p_arith_expr2(p):
    ''' arith_expr : term arith_expr_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node


def p_arith_expr_list1(p):
    ''' arith_expr_list : arith_op '''
    p[0] = [p[1]]


def p_arith_expr_list2(p):
    ''' arith_expr_list : arith_expr_list arith_op '''
    p[0] = p[1] + [p[2]]


def p_arith_op1(p):
    ''' arith_op : PLUS term '''
    node = ast.Add()
    p[0] = [node, p[2]]


def p_arith_op2(p):
    ''' arith_op : MINUS term '''
    p[0] = [ast.Sub(), p[2]]


def p_term1(p):
    ''' term : factor '''
    p[0] = p[1]


def p_term2(p):
    ''' term : factor term_list '''
    node = p[1]
    for op, right in p[2]:
        node = ast.BinOp(left=node, op=op, right=right)
    p[0] = node


def p_term_list1(p):
    ''' term_list : term_op '''
    p[0] = [p[1]]


def p_term_list2(p):
    ''' term_list : term_list term_op '''
    p[0] = p[1] + [p[2]]


def p_term_op1(p):
    ''' term_op : STAR factor '''
    p[0] = [ast.Mult(), p[2]]


def p_term_op2(p):
    ''' term_op : SLASH factor '''
    p[0] = [ast.Div(), p[2]]


def p_term_op3(p):
    ''' term_op : PERCENT factor '''
    p[0] = [ast.Mod(), p[2]]


def p_term_op4(p):
    ''' term_op : DOUBLESLASH factor '''
    p[0] = [ast.FloorDiv(), p[2]]


def p_factor1(p):
    ''' factor : power '''
    p[0] = p[1]


def p_factor2(p):
    ''' factor : PLUS factor '''
    op = ast.UAdd()
    operand = p[2]
    node = ast.UnaryOp(op=op, operand=operand)
    p[0] = node


def p_factor3(p):
    ''' factor : MINUS factor '''
    op = ast.USub()
    operand = p[2]
    node = ast.UnaryOp(op=op, operand=operand)
    p[0] = node


def p_factor4(p):
    ''' factor : TILDE factor '''
    op = ast.Invert()
    operand = p[2]
    node = ast.UnaryOp(op=op, operand=operand)
    p[0] = node


def p_power1(p):
    ''' power : atom '''
    p[0] = p[1]


def p_power2(p):
    ''' power : atom DOUBLESTAR factor '''
    node = ast.BinOp(left=p[1], op=ast.Pow(), right=p[3])
    p[0] = node


def p_power3(p):
    ''' power : atom power_list '''
    root = p[1]
    for node in p[2]:
        if isinstance(node, ast.Call):
            node.func = root
        elif isinstance(node, ast.Attribute):
            node.value = root
        elif isinstance(node, ast.Subscript):
            node.value = root
        else:
            raise TypeError('Unexpected trailer node: %s' % node)
        root = node
    p[0] = root


def p_power4(p):
    ''' power : atom power_list DOUBLESTAR factor '''
    root = p[1]
    for node in p[2]:
        if isinstance(node, ast.Call):
            node.func = root
        elif isinstance(node, ast.Attribute):
            node.value = root
        elif isinstance(node, ast.Subscript):
            node.value = root
        else:
            raise TypeError('Unexpected trailer node: %s' % node)
        root = node
    power = ast.BinOp(left=root, op=ast.Pow(), right=p[4])
    p[0] = power


def p_power_list1(p):
    ''' power_list : trailer '''
    p[0] = [p[1]]


def p_power_list2(p):
    ''' power_list : power_list trailer '''
    p[0] = p[1] + [p[2]]


def p_atom1(p):
    ''' atom : LPAR RPAR '''
    p[0] = ast.Tuple(elts=[], ctx=ast.Load())


def p_atom2(p):
    ''' atom : LPAR testlist_comp RPAR '''
    info = p[2]
    if isinstance(info, CommaSeparatedList):
        node = ast.Tuple(elts=info.values, ctx=ast.Load())
    elif isinstance(info, GeneratorInfo):
        node = ast.GeneratorExp(elt=info.elt, generators=info.generators)
    else:
        # We have a test node by itself in parenthesis controlling 
        # order of operations, so just return the node.
        node = info
    p[0] = node


def p_atom3(p):
    ''' atom : LSQB RSQB '''
    p[0] = ast.List(elts=[], ctx=ast.Load())


def p_atom4(p):
    ''' atom : LSQB listmaker RSQB '''
    info = p[2]
    if isinstance(info, CommaSeparatedList):
        node = ast.List(elts=info.values, ctx=ast.Load())
    elif isinstance(info, GeneratorInfo):
        node = ast.ListComp(elt=info.elt, generators=info.generators)
    else:
        raise TypeError('Unexpected node for listmaker: %s' % info)
    p[0] = node
    

def p_atom5(p):
    ''' atom : LBRACE RBRACE '''
    p[0] = ast.Dict(keys=[], values=[])


def p_atom6(p):
    ''' atom : LBRACE dictorsetmaker RBRACE '''
    info = p[2]
    if isinstance(info, GeneratorInfo):
        if isinstance(info.elt, tuple):
            key, value = info.elt
            generators = info.generators
            node = ast.DictComp(key=key, value=value, generators=generators)
        else:
            node = ast.SetComp(elt=info.elt, generators=info.generators)
    elif isinstance(info, CommaSeparatedList):
        if isinstance(info.values[0], tuple):
            keys, values = zip(*info.values)
            node = ast.Dict(keys=list(keys), values=list(values))
        else:
            node = ast.Set(elts=info.values)
    else:
        raise TypeError('Unexpected node for dictorsetmaker: %s' % info)
    p[0] = node


def p_atom7(p):
    ''' atom : NAME '''
    p[0] = ast.Name(id=p[1], ctx=ast.Load())


def p_atom8(p):
    ''' atom : NUMBER '''
    n = ast.Num(n=eval(p[1]))
    p[0] = n


def p_atom9(p):
    ''' atom : atom_string_list '''
    s = ast.Str(s=p[1])
    p[0] = s


def p_atom_string_list1(p):
    ''' atom_string_list : STRING '''
    p[0] = p[1]


def p_atom_string_list2(p):
    ''' atom_string_list : atom_string_list STRING '''
    p[0] = p[1] + p[2]


# We dont' allow the backqoute atom from standard Python. Just
# use repr(...). This simplifies the grammar since we don't have 
# to define a testlist1.


def p_listmaker1(p):
    ''' listmaker : test list_for '''
    p[0] = GeneratorInfo(elt=p[1], generators=p[2])


def p_listmaker2(p):
    ''' listmaker : test '''
    p[0] = CommaSeparatedList(values=[p[1]])


def p_listmaker3(p):
    ''' listmaker : test COMMA '''
    p[0] = CommaSeparatedList(values=[p[1]])


def p_listmaker4(p):
    ''' listmaker : test listmaker_list '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_listmaker5(p):
    ''' listmaker : test listmaker_list COMMA '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_listmaker_list1(p):
    ''' listmaker_list : COMMA test '''
    p[0] = [p[2]]


def p_listmaker_list2(p):
    ''' listmaker_list : listmaker_list COMMA test '''
    p[0] = p[1] + [p[3]]


def p_testlist_comp1(p):
    ''' testlist_comp : test comp_for '''
    p[0] = GeneratorInfo(elt=p[1], generators=p[2])


def p_testlist_comp2(p):
    ''' testlist_comp : test '''
    p[0] = p[1]


def p_testlist_comp3(p):
    ''' testlist_comp : test COMMA '''
    p[0] = CommaSeparatedList(values=[p[1]])


def p_testlist_comp4(p):
    ''' testlist_comp : test testlist_comp_list '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_testlist_comp5(p):
    ''' testlist_comp : test testlist_comp_list COMMA '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_testlist_comp_list1(p):
    ''' testlist_comp_list : COMMA test '''
    p[0] = [p[2]]


def p_testlist_comp_list2(p):
    ''' testlist_comp_list : testlist_comp_list COMMA test '''
    p[0] = p[1] + [p[3]]


def p_trailer1(p):
    ''' trailer : LPAR RPAR '''
    p[0] = ast.Call(args=[], keywords=[], starargs=None, kwargs=None)


def p_trailer2(p):
    ''' trailer : LPAR arglist RPAR '''
    args = p[2]
    p[0] = ast.Call(args=args.args, keywords=args.keywords, 
                    starargs=args.starargs, kwargs=args.kwargs) 


def p_trailer3(p):
    ''' trailer : LSQB subscriptlist RSQB '''
    p[0] = ast.Subscript(slice=p[2], ctx=ast.Load())


def p_trailer4(p):
    ''' trailer : DOT NAME '''
    p[0] = ast.Attribute(attr=p[2], ctx=ast.Load())
    

def p_subscriptlist1(p):
    ''' subscriptlist : subscript '''
    p[0] = p[1]


def p_subscriptlist2(p):
    ''' subscriptlist : subscript COMMA '''
    dims = [p[1]]
    p[0] = ast.ExtSlice(dims=dims)


def p_subscriptlist3(p):
    ''' subscriptlist : subscript subscriptlist_list '''
    dims = [p[1]] + p[2]
    p[0] = ast.ExtSlice(dims=dims)


def p_subscriptlist4(p):
    ''' subscriptlist : subscript subscriptlist_list COMMA '''
    dims = [p[1]] + p[2]
    p[0] = ast.ExtSlice(dims=dims)


def p_subscriptlist_list1(p):
    ''' subscriptlist_list : COMMA subscript '''
    p[0] = [p[2]]


def p_subscript_list2(p):
    ''' subscriptlist_list : subscriptlist_list COMMA subscript '''
    p[0] = p[1] + [p[2]]


def p_subscript1(p):
    ''' subscript : ELLIPSIS '''
    p[0] = ast.Ellipsis()


def p_subcript2(p):
    ''' subscript : test '''
    p[0] = ast.Index(value=p[1])


def p_subscript3(p):
    ''' subscript : COLON '''
    p[0] = ast.Slice(lower=None, upper=None, step=None)


def p_subscript4(p):
    ''' subscript : DOUBLECOLON '''
    name = ast.Name(id='None', ctx=ast.Load())
    p[0] = ast.Slice(lower=None, upper=None, step=name)


def p_subscript5(p):
    ''' subscript : test COLON '''
    p[0] = ast.Slice(lower=p[1], uppper=None, step=None)


def p_subscrip6(p):
    ''' subscript : test DOUBLECOLON '''
    name = ast.Name(id='None', ctx=ast.Load())
    p[0] = ast.Slice(lower=p[1], upper=None, step=name)


def p_subscript7(p):
    ''' subscript : COLON test '''
    p[0] = ast.Slice(lower=None, upper=p[2], step=None)


def p_subscript8(p):
    ''' subscript : COLON test COLON '''
    name = ast.Name(id='None', ctx=ast.Load())
    p[0] = ast.Slice(lower=None, upper=p[2], step=name)


def p_subscript9(p):
    ''' subscript : DOUBLECOLON test '''
    p[0] = ast.Slice(lower=None, upper=None, step=p[2])


def p_subscript10(p):
    ''' subscript : test COLON test '''
    p[0] = ast.Slice(lower=p[1], uppper=p[3], step=None)


def p_subscript11(p):
    ''' subscript : test COLON test COLON '''
    name = ast.Name(id='None', ctx=ast.Load())
    p[0] = ast.Slice(lower=p[1], upper=p[3], step=name)


def p_subscript12(p):
    ''' subscript : COLON test COLON test '''
    p[0] = ast.Slice(lower=None, upper=p[2], step=p[4])


def p_subscript13(p):
    ''' subscript : test COLON test COLON test '''
    p[0] = ast.Slice(lower=p[1], upper=p[3], step=p[5])


def p_subscript14(p):
    ''' subscript : test DOUBLECOLON test '''
    p[0] = ast.Slice(lower=p[1], upper=None, step=p[3])


def p_exprlist1(p):
    ''' exprlist : expr '''
    # expr will match a tuple or a name, so we need to handle 
    # the store context for both.
    expr = p[1]
    set_store_ctxt(expr)
    p[0] = expr


def p_exprlist2(p):
    ''' exprlist : expr COMMA '''
    exprs = [p[1]]
    tup = ast.Tuple()
    tup.elts = exprs
    set_store_ctxt(tup)
    p[0] = tup


def p_exprlist3(p):
    ''' exprlist : expr exprlist_list '''
    exprs = [p[1]] + p[2]
    tup = ast.Tuple()
    tup.elts = exprs
    set_store_ctxt(tup)
    p[0] = tup


def p_exprlist4(p):
    ''' exprlist : expr exprlist_list COMMA '''
    exprs = [p[1]] + p[2]
    tup = ast.Tuple()
    tup.elts = exprs
    set_store_ctxt(tup)
    p[0] = tup


def p_exprlist_list1(p):
    ''' exprlist_list : COMMA expr '''
    p[0] = [p[2]]


def p_exprlist_list2(p):
    ''' exprlist_list : exprlist_list COMMA expr '''
    p[0] = p[1] + [p[3]]


def p_dictorsetmaker1(p):
    ''' dictorsetmaker : test COLON test comp_for '''
    p[0] = GeneratorInfo(elt=(p[1], p[3]), generators=p[4])


def p_dictorsetmaker2(p):
    ''' dictorsetmaker : test COLON test '''
    values = [(p[1], p[3])]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker3(p):
    ''' dictorsetmaker : test COLON test COMMA '''
    values = [(p[1], p[3])]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker4(p):
    ''' dictorsetmaker : test COLON test dosm_colon_list '''
    values = [(p[1], p[3])] + p[4]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker5(p):
    ''' dictorsetmaker : test COLON test dosm_colon_list COMMA '''
    values = [(p[1], p[3])] + p[4]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker6(p):
    ''' dictorsetmaker : test comp_for '''
    p[0] = GeneratorInfo(elt=p[1], generators=p[2])


def p_dictorsetmaker7(p):
    ''' dictorsetmaker : test COMMA '''
    values = [p[1]]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker8(p):
    ''' dictorsetmaker : test dosm_comma_list '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_dictorsetmaker9(p):
    ''' dictorsetmaker : test dosm_comma_list COMMA '''
    values = [p[1]] + p[2]
    p[0] = CommaSeparatedList(values=values)


def p_dosm_colon_list1(p):
    ''' dosm_colon_list : COMMA test COLON test '''
    p[0] = [(p[2], p[4])]


def p_dosm_colon_list2(p):
    ''' dosm_colon_list : dosm_colon_list COMMA test COLON test '''
    p[0] = p[1] + [(p[3], p[5])]


def p_dosm_comma_list1(p):
    ''' dosm_comma_list : COMMA test '''
    p[0] = [p[1]]


def p_dosm_comma_list2(p):
    ''' dosm_comma_list : dosm_comma_list COMMA test '''
    p[0] = p[1] + [p[3]]


def p_arglist1(p):
    ''' arglist : argument '''
    if isinstance(p[1], ast.keyword):
        p[0] = Arguments(keywords=[p[1]])
    else:
        p[0] = Arguments(args=[p[1]])


def p_arglist2(p):
    ''' arglist : argument COMMA '''
    if isinstance(p[1], ast.keyword):
        p[0] = Arguments(keywords=[p[1]])
    else:
        p[0] = Arguments(args=[p[1]])


def p_arglist3(p):
    ''' arglist : STAR test '''
    p[0] = Arguments(starargs=p[2])


def p_arglist4(p):
    ''' arglist : STAR test COMMA DOUBLESTAR test '''
    p[0] = Arguments(starargs=p[2], kwargs=p[5])


def p_arglist5(p):
    ''' arglist : DOUBLESTAR test '''
    p[0] = Arguments(kwargs=p[2])


def p_arglist6(p):
    ''' arglist : arglist_list argument '''
    args = []
    kws = []
    for arg in (p[1] + [p[2]]):
        if isinstance(arg, ast.keyword):
            kws.append(arg)
        else:
            args.append(arg)
    p[0] = Arguments(args=args, keywords=kws)


def p_arglist7(p):
    ''' arglist : arglist_list argument COMMA '''
    args = []
    kws = []
    for arg in (p[1] + [p[2]]):
        if isinstance(arg, ast.keyword):
            kws.append(arg)
        else:
            args.append(arg)
    p[0] = Arguments(args=args, keywords=kws)


def p_arglist8(p):
    ''' arglist : arglist_list STAR test '''
    args = []
    kws = []
    for arg in p[1]:
        if isinstance(arg, ast.keyword):
            kws.append(arg)
        else:
            args.append(arg)
    p[0] = Arguments(args=args, keywords=kws, starargs=p[3])


def p_arglist9(p):
    ''' arglist : arglist_list STAR test COMMA DOUBLESTAR test '''
    args = []
    kws = []
    for arg in p[1]:
        if isinstance(arg, ast.keyword):
            kws.append(arg)
        else:
            args.append(arg)
    p[0] = Arguments(args=args, keywords=kws, starargs=p[3], kwargs=p[6])


def p_arglist10(p):
    ''' arglist : arglist_list DOUBLESTAR test '''
    args = []
    kws = []
    for arg in p[1]:
        if isinstance(arg, ast.keyword):
            kws.append(arg)
        else:
            args.append(arg)
    p[0] = Arguments(args=args, keywords=kws, kwargs=p[3])


def p_arglist_list1(p):
    ''' arglist_list : argument COMMA '''
    p[0] = [p[1]]


def p_arglist_list2(p):
    ''' arglist_list : arglist_list argument COMMA '''
    p[0] = p[1] + [p[2]]


def p_argument1(p):
    ''' argument : test '''
    p[0] = p[1]


def p_argument2(p):
    ''' argument : test comp_for '''
    p[0] = ast.GeneratorExp(elt=p[1], generators=p[2]) 


# This keyword argument needs to be asserted as a NAME, but using NAME
# here causes ambiguity in the parse tables.
def p_argument3(p):
    ''' argument : test EQUAL test '''
    arg = p[1]
    assert isinstance(arg, ast.Name), 'Keyword arg must be a Name.'
    value = p[3]
    p[0] = ast.keyword(arg=arg.id, value=value)


def p_list_for1(p):
    ''' list_for : FOR exprlist IN testlist_safe '''
    p[0] = [ast.comprehension(target=p[2], iter=p[4], ifs=[])]


def p_list_for2(p):
    ''' list_for : FOR exprlist IN testlist_safe list_iter '''
    gens = []
    gens.append(ast.comprehension(target=p[2], iter=p[4], ifs=[]))
    for item in p[5]:
        if isinstance(item, ast.comprehension):
            gens.append(item)
        else:
            gens[-1].ifs.append(item)
    p[0] = gens


def p_list_iter1(p):
    ''' list_iter : list_for '''
    p[0] = p[1]


def p_list_iter2(p):
    ''' list_iter : list_if '''
    p[0] = p[1]


def p_list_if1(p):
    ''' list_if : IF old_test '''
    p[0] = [p[2]]


def p_list_if2(p):
    ''' list_if : IF old_test list_iter '''
    p[0] = [p[2]] + p[3]


def p_comp_for1(p):
    ''' comp_for : FOR exprlist IN or_test '''
    p[0] = [ast.comprehension(target=p[2], iter=p[4], ifs=[])]


def p_comp_for2(p):
    ''' comp_for : FOR exprlist IN or_test comp_iter '''
    gens = []
    gens.append(ast.comprehension(target=p[2], iter=p[4], ifs=[]))
    for item in p[5]:
        if isinstance(item, ast.comprehension):
            gens.append(item)
        else:
            gens[-1].ifs.append(item)
    p[0] = gens


def p_comp_iter1(p):
    ''' comp_iter : comp_for '''
    p[0] = p[1]


def p_comp_iter2(p):
    ''' comp_iter : comp_if '''
    p[0] = p[1]


def p_comp_if1(p):
    ''' comp_if : IF old_test '''
    p[0] = [p[2]]


def p_comp_if2(p):
    ''' comp_if : IF old_test comp_iter '''
    p[0] = [p[2]] + p[3]


def p_testlist_safe1(p):
    ''' testlist_safe : old_test '''
    p[0] = p[1]


def p_testlist_safe2(p):
    ''' testlist_safe : old_test testlist_safe_list '''
    values = [p[1]] + p[2]
    p[0] = ast.Tuple(elts=values, ctx=ast.Load())


def p_testlist_safe3(p):
    ''' testlist_safe : old_test testlist_safe_list COMMA '''
    values = [p[1]] + p[2]
    p[0] = ast.Tuple(elts=values, ctx=ast.Load())


def p_testlist_safe_list1(p):
    ''' testlist_safe_list : COMMA old_test '''
    p[0] = [p[2]]


def p_testlist_safe_list2(p):
    ''' testlist_safe_list : testlist_safe_list COMMA old_test '''
    p[0] = p[1] + [p[2]]


def p_old_test1(p):
    ''' old_test : or_test '''
    p[0] = p[1]


def p_old_test2(p):
    ''' old_test : old_lambdef '''
    p[0] = p[1]


def p_old_lambdef1(p):
    ''' old_lambdef : LAMBDA COLON old_test '''
    args = ast.arguments(args=[], defaults=[], kwarg=None, vararg=None)
    body = p[3]
    p[0] = ast.Lambda(args=args, body=body)


def p_old_lambdef2(p):
    ''' old_lambdef : LAMBDA varargslist COLON old_test '''
    args = p[2]
    body = p[4]
    p[0] = ast.Lambda(args=args, body=body)


def p_lambdef1(p):
    ''' lambdef : LAMBDA COLON test '''
    args = ast.arguments(args=[], defaults=[], kwarg=None, vararg=None)
    body = p[3]
    p[0] = ast.Lambda(args=args, body=body)


def p_lambdef2(p):
    ''' lambdef : LAMBDA varargslist COLON test '''
    args = p[2]
    body = p[4]
    p[0] = ast.Lambda(args=args, body=body)


def p_varargslist1(p):
    ''' varargslist : fpdef COMMA STAR NAME '''
    # def f(a, *args): pass
    # def f((a, b), *args): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[], vararg=p[4], kwarg=None)


def p_varargslist2(p):
    ''' varargslist : fpdef COMMA STAR NAME COMMA DOUBLESTAR NAME '''
    # def f(a, *args, **kwargs): pass
    # def f((a, b), *args, **kwargs): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[], vararg=p[4], kwarg=p[7])


def p_varargslist3(p):
    ''' varargslist : fpdef COMMA DOUBLESTAR NAME '''
    # def f(a, **kwargs): pass
    # def f((a, b), **kwargs): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[], vararg=None, kwarg=p[4])


def p_varargslist4(p):
    ''' varargslist : fpdef '''
    # def f(a): pass
    # def f((a, b)): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[], vararg=None, kwarg=None)


def p_varargslist5(p):
    ''' varargslist : fpdef COMMA '''
    # def f(a,): pass
    # def f((a,b),): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[], vararg=None, kwarg=None)


def p_varargslist6(p):
    ''' varargslist : fpdef varargslist_list COMMA STAR NAME '''
    # def f((a, b), c, *args): pass
    # def f((a, b), c, d=4, *args): pass
    list_args, defaults = p[2]
    args = [p[1]] + list_args
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=p[5], kwarg=None)


def p_varargslist7(p):
    ''' varargslist : fpdef varargslist_list COMMA STAR NAME COMMA DOUBLESTAR NAME '''
    # def f((a, b), c, *args, **kwargs): pass
    # def f((a, b), c, d=4, *args, **kwargs): pass
    list_args, defaults = p[2]
    args = [p[1]] + list_args
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=p[5], kwarg=p[8])


def p_varargslist8(p):
    ''' varargslist : fpdef varargslist_list COMMA DOUBLESTAR NAME '''
    # def f((a, b), c, **kwargs): pass
    # def f((a, b), c, d=4, **kwargs): pass
    list_args, defaults = p[2]
    args = [p[1]] + list_args
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=p[5])


def p_varargslist9(p):
    ''' varargslist : fpdef varargslist_list '''
    # def f((a, b), c): pass
    # def f((a, b), c, d=4): pass
    list_args, defaults = p[2]
    args = [p[1]] + list_args
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=None)


def p_varargslist10(p):
    ''' varargslist : fpdef varargslist_list COMMA '''
    # def f((a, b), c,): pass
    # def f((a, b), c, d=4,): pass
    list_args, defaults = p[2]
    args = [p[1]] + list_args
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=None)


def p_varargslist11(p):
    ''' varargslist : fpdef EQUAL test COMMA STAR NAME '''
    # def f(a=1, *args): pass
    # def f((a,b)=(1,2), *args): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[p[3]], vararg=p[6], kwarg=None)


def p_varargslist12(p):
    ''' varargslist : fpdef EQUAL test COMMA STAR NAME COMMA DOUBLESTAR NAME '''
    # def f(a=1, *args, **kwargs): pass
    # def f((a,b)=(1,2), *args, **kwargs): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[p[3]], vararg=p[6], kwarg=p[9])


def p_varargslist13(p):
    ''' varargslist : fpdef EQUAL test COMMA DOUBLESTAR NAME '''
    # def f(a=1, **kwargs): pass
    # def f((a,b)=(1,2), **kwargs): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[p[3]], vararg=None, kwarg=p[6])


def p_varargslist14(p):
    ''' varargslist : fpdef EQUAL test '''
    # def f(a=1): pass
    # def f((a,b)=(1,2)): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[p[3]], vararg=None, kwarg=None)


def p_varargslist15(p):
    ''' varargslist : fpdef EQUAL test COMMA '''
    # def f(a=1,): pass
    # def f((a,b)=(1,2),): pass
    p[0] = ast.arguments(args=[p[1]], defaults=[p[3]], vararg=None, kwarg=None)


def p_varargslist16(p):
    ''' varargslist : fpdef EQUAL test varargslist_list COMMA STAR NAME '''
    # def f(a=1, b=2, *args): pass
    list_args, list_defaults = p[4]
    args = [p[1]] + list_args
    defaults = [p[3]] + list_defaults
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=p[7], kwarg=None)


def p_varargslist17(p):
    ''' varargslist : fpdef EQUAL test varargslist_list COMMA STAR NAME COMMA DOUBLESTAR NAME '''
    # def f(a=1, b=2, *args, **kwargs)
    list_args, list_defaults = p[4]
    args = [p[1]] + list_args
    defaults = [p[3]] + list_defaults
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=p[7], kwarg=p[10])


def p_varargslist18(p):
    ''' varargslist : fpdef EQUAL test varargslist_list COMMA DOUBLESTAR NAME '''
    # def f(a=1, b=2, **kwargs): pass
    list_args, list_defaults = p[4]
    args = [p[1]] + list_args
    defaults = [p[3]] + list_defaults
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=p[7])


def p_varargslist19(p):
    ''' varargslist : fpdef EQUAL test varargslist_list '''
    # def f(a=1, b=2): pass
    list_args, list_defaults = p[4]
    args = [p[1]] + list_args
    defaults = [p[3]] + list_defaults
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=None)


def p_varargslist20(p):
    ''' varargslist : fpdef EQUAL test varargslist_list COMMA '''
    # def f(a=1, b=2,): pass
    list_args, list_defaults = p[4]
    args = [p[1]] + list_args
    defaults = [p[3]] + list_defaults
    p[0] = ast.arguments(args=args, defaults=defaults, vararg=None, kwarg=None)


def p_varargslist21(p):
    ''' varargslist : STAR NAME '''
    # def f(*args): pass
    p[0] = ast.arguments(args=[], defaults=[], vararg=p[2], kwarg=None)


def p_varargslist22(p):
    ''' varargslist : STAR NAME COMMA DOUBLESTAR NAME '''
    # def f(*args, **kwargs): pass
    p[0] = ast.arguments(args=[], defaults=[], vararg=p[2], kwarg=p[5])


def p_varargslist23(p):
    ''' varargslist : DOUBLESTAR NAME '''
    # def f(**kwargs): pass
    p[0] = ast.arguments(args=[], defaults=[], vararg=None, kwarg=p[2])


# The varargslist_list handlers return a 2-tuple of (args, defaults) lists
def p_varargslist_list1(p):
    ''' varargslist_list : COMMA fpdef '''
    p[0] = ([p[2]], [])


def p_varargslist_list2(p):
    ''' varargslist_list : COMMA fpdef EQUAL test '''
    p[0] = ([p[2]], [p[4]])


def p_varargslist_list3(p):
    ''' varargslist_list : varargslist_list COMMA fpdef '''
    list_args, list_defaults = p[1]
    if list_defaults:
        raise SyntaxError('non-default argument follows default argument.')
    args = list_args + [p[3]]
    p[0] = (args, list_defaults)


def p_varargslist_list4(p):
    ''' varargslist_list : varargslist_list COMMA fpdef EQUAL test '''
    list_args, list_defaults = p[1]
    args = list_args + [p[3]]
    defaults = list_defaults +[p[5]]
    p[0] = (args, defaults)


def p_fpdef1(p):
    ''' fpdef : NAME '''
    p[0] = ast.Name(id=p[1], ctx=ast.Param())


def p_fpdef2(p):
    ''' fpdef : LPAR fplist RPAR '''
    # fplist will return a NAME or a TUPLE, so we don't need that
    # logic here.
    p[0] = p[2]


def p_fplist1(p):
    ''' fplist : fpdef '''
    p[0] = p[1]


def p_fplist2(p):
    ''' fplist : fpdef COMMA '''
    tup = ast.Tuple()
    tup.elts = [p[1]]
    set_store_ctxt(tup)
    p[0] = tup


def p_fplist3(p):
    ''' fplist : fpdef fplist_list '''
    elts = [p[1]] + p[2]
    tup = ast.Tuple()
    tup.elts = elts
    set_store_ctxt(tup)
    p[0] = tup


def p_fplist4(p):
    ''' fplist : fpdef fplist_list COMMA '''
    elts = [p[1]] + p[2]
    tup = ast.Tuple()
    tup.elts = elts
    set_store_ctxt(tup)
    p[0] = tup


def p_fplist_list1(p):
    ''' fplist_list : COMMA fpdef '''
    p[0] = [p[2]]
  

def p_fplist_list2(p):
    ''' fplist_list : fplist_list COMMA fpdef '''
    p[0] = p[1] + [p[3]]

 
def p_error(t):
    raise_syntax_error('invalid syntax.', t.lexer.filename, t.lineno)


_parser = yacc.yacc(debug=False, tabmodule='enaml_parsetab', 
                    outputdir=_enaml_dir, errorlog=yacc.NullLogger())


def parse(enaml_source, filename='Enaml'):
    _lexer = EnamlLexer(filename)
    return _parser.parse(enaml_source, lexer=_lexer)
