#
# The main tests for the code in single.py are currently located in
# sympy/solvers/tests/test_ode.py
#
r"""
This File contains test functions for the individual hints used for solving ODEs.

Examples of each solver will be returned by _get_examples_ode_sol_name_of_solver.

Examples should have a key 'XFAIL' which stores the list of hints if they are
expected to fail for that hint.

Functions that are for internal use:

1) _ode_solver_test(ode_examples) - It takes dictionary of examples returned by
   _get_examples method and tests them with their respective hints.

2) _test_particular_example(our_hint, example_name) - It tests the ODE example corresponding
   to the hint provided.

3) _test_all_hints(runxfail=False) - It is used to test all the examples with all the hints
  currently implemented. It calls _test_all_examples_for_one_hint() which outputs whether the
  given hint functions properly if it classifies the ODE example.
  If runxfail flag is set to True then it will only test the examples which are expected to fail.

  Everytime the ODE of partiular solver are added then _test_all_hints() is to execuetd to find
  the possible failures of different solver hints.

4) _test_all_examples_for_one_hint(our_hint, all_examples) - It takes hint as argument and checks
   this hint against all the ODE examples and gives output as the number of ODEs matched, number
   of ODEs which were solved correctly, list of ODEs which gives incorrect solution and list of
   ODEs which raises exception.

"""
from sympy import (acos, asin, asinh, atan, cos, Derivative, Dummy, diff,
    E, Eq, exp, hyper, I, Integral, integrate, LambertW, log, pi, Piecewise, Rational, S, sin, sinh, tan,
    sqrt, symbols, Ei, erfi)

from sympy.core import Function, Symbol
from sympy.functions import airyai, airybi, besselj, bessely
from sympy.integrals.risch import NonElementaryIntegral
from sympy.solvers.ode import classify_ode, dsolve
from sympy.solvers.ode.ode import allhints, _remove_redundant_solutions
from sympy.solvers.ode.single import (FirstLinear, ODEMatchError,
    SingleODEProblem, SingleODESolver)

from sympy.solvers.ode.subscheck import checkodesol

from sympy.testing.pytest import raises, slow, ON_TRAVIS
import traceback


x = Symbol('x')
u = Symbol('u')
y = Symbol('y')
f = Function('f')
g = Function('g')
C1, C2, C3, C4, C5 = symbols('C1:6')


hint_message = """\
Hint did not match the example {example}.

The ODE is:
{eq}.

The expected hint was
{our_hint}\
"""

expected_sol_message = """\
Different solution found from dsolve for example {example}.

The ODE is:
{eq}

The expected solution was
{sol}

What dsolve returned is:
{dsolve_sol}\
"""

checkodesol_msg = """\
solution found is not correct for example {example}.

The ODE is:
{eq}\
"""

dsol_incorrect_msg = """\
solution returned by dsolve is incorrect when using {hint}.

The ODE is:
{eq}

The expected solution was
{sol}

what dsolve returned is:
{dsolve_sol}

You can test this with:

eq = {eq}
sol = dsolve(eq, hint='{hint}')
print(sol)
print(checkodesol(eq, sol))

"""

exception_msg = """\
dsolve raised exception : {e}

when using {hint} for the example {example}

You can test this with:

from sympy.solvers.ode.tests.test_single import _test_an_example

_test_an_example('{hint}', example_name = '{example}')

The ODE is:
{eq}

\
"""

check_hint_msg = """\
Tested hint was : {hint}

Total of {matched} examples matched with this hint.

Out of which {solve} gave correct results.

Examples which gave incorrect results are {unsolve}.

Examples which raised exceptions are {exceptions}
\
"""


def _add_example_keys(func):
    def inner():
        solver=func()
        examples=[]
        for example in solver['examples']:
            temp={
                'eq': solver['examples'][example]['eq'],
                'sol': solver['examples'][example]['sol'],
                'XFAIL': solver['examples'][example].get('XFAIL', []),
                'func': solver['examples'][example].get('func',solver['func']),
                'example_name': example,
                'slow': solver['examples'][example].get('slow', False),
                'simplify_flag':solver['examples'][example].get('simplify_flag',True),
                'checkodesol_XFAIL': solver['examples'][example].get('checkodesol_XFAIL', False),
                'dsolve_too_slow':solver['examples'][example].get('dsolve_too_slow',False),
                'checkodesol_too_slow':solver['examples'][example].get('checkodesol_too_slow',False),
                'hint': solver['hint']
            }
            examples.append(temp)
        return examples
    return inner()


def _ode_solver_test(ode_examples, run_slow_test=False):
    for example in ode_examples:
        if ((not run_slow_test) and example['slow']) or (run_slow_test and (not example['slow'])):
            continue

        result = _test_particular_example(example['hint'], example, solver_flag=True)
        if result['xpass_msg'] != "":
            print(result['xpass_msg'])


def _test_all_hints(runxfail=False):
    all_hints = list(allhints)+["default"]
    all_examples = _get_all_examples()

    for our_hint in all_hints:
        if our_hint.endswith('_Integral') or 'series' in our_hint:
            continue
        _test_all_examples_for_one_hint(our_hint, all_examples, runxfail)


def _test_dummy_sol(expected_sol,dsolve_sol):
    if type(dsolve_sol)==list:
        return any(expected_sol.dummy_eq(sub_dsol) for sub_dsol in dsolve_sol)
    else:
        return expected_sol.dummy_eq(dsolve_sol)


def _test_an_example(our_hint, example_name):
    all_examples = _get_all_examples()
    for example in all_examples:
        if example['example_name'] == example_name:
            _test_particular_example(our_hint, example)


def _test_particular_example(our_hint, ode_example, solver_flag=False):
    eq = ode_example['eq']
    expected_sol = ode_example['sol']
    example = ode_example['example_name']
    xfail = our_hint in ode_example['XFAIL']
    func = ode_example['func']
    result = {'msg': '', 'xpass_msg': ''}
    simplify_flag=ode_example['simplify_flag']
    checkodesol_XFAIL = ode_example['checkodesol_XFAIL']
    dsolve_too_slow = ode_example['dsolve_too_slow']
    checkodesol_too_slow = ode_example['checkodesol_too_slow']
    xpass = True
    if solver_flag:
        if our_hint not in classify_ode(eq, func):
            message = hint_message.format(example=example, eq=eq, our_hint=our_hint)
            raise AssertionError(message)

    if our_hint in classify_ode(eq, func):
        result['match_list'] = example
        try:
            if not (dsolve_too_slow and ON_TRAVIS):
                dsolve_sol = dsolve(eq, func, simplify=simplify_flag,hint=our_hint)
            else:
                if len(expected_sol)==1:
                    dsolve_sol = expected_sol[0]
                else:
                    dsolve_sol = expected_sol

        except Exception as e:
            dsolve_sol = []
            result['exception_list'] = example
            if not solver_flag:
                traceback.print_exc()
                result['msg'] = exception_msg.format(e=str(e), hint=our_hint, example=example, eq=eq)
            xpass = False

        if solver_flag and dsolve_sol!=[]:
            expect_sol_check = False
            if type(dsolve_sol)==list:
                for sub_sol in expected_sol:
                    if sub_sol.has(Dummy):
                        expect_sol_check = not _test_dummy_sol(sub_sol, dsolve_sol)
                    else:
                        expect_sol_check = sub_sol not in dsolve_sol
                    if expect_sol_check:
                        break
            else:
                expect_sol_check = dsolve_sol not in expected_sol
                for sub_sol in expected_sol:
                    if sub_sol.has(Dummy):
                        expect_sol_check = not _test_dummy_sol(sub_sol, dsolve_sol)

            if expect_sol_check:
                message = expected_sol_message.format(example=example, eq=eq, sol=expected_sol, dsolve_sol=dsolve_sol)
                raise AssertionError(message)

            expected_checkodesol = [(True, 0) for i in range(len(expected_sol))]
            if len(expected_sol) == 1:
                expected_checkodesol = (True, 0)

            if not (checkodesol_too_slow and ON_TRAVIS):
                if not checkodesol_XFAIL:
                    if checkodesol(eq, dsolve_sol, solve_for_func=False) != expected_checkodesol:
                        result['unsolve_list'] = example
                        xpass = False
                        message = dsol_incorrect_msg.format(hint=our_hint, eq=eq, sol=expected_sol,dsolve_sol=dsolve_sol)
                        if solver_flag:
                            message = checkodesol_msg.format(example=example, eq=eq)
                            raise AssertionError(message)
                        else:
                            result['msg'] = 'AssertionError: ' + message

        if xpass and xfail:
            result['xpass_msg'] = example + "is now passing for the hint" + our_hint
    return result


def _test_all_examples_for_one_hint(our_hint, all_examples=[], runxfail=None):
    if all_examples == []:
        all_examples = _get_all_examples()
    match_list, unsolve_list, exception_list = [], [], []
    for ode_example in all_examples:
        xfail = our_hint in ode_example['XFAIL']
        if runxfail and not xfail:
            continue
        if xfail:
            continue
        result = _test_particular_example(our_hint, ode_example)
        match_list += result.get('match_list',[])
        unsolve_list += result.get('unsolve_list',[])
        exception_list += result.get('exception_list',[])
        if runxfail is not None:
            msg = result['msg']
            if msg!='':
                print(result['msg'])
            # print(result.get('xpass_msg',''))
    if runxfail is None:
        match_count = len(match_list)
        solved = len(match_list)-len(unsolve_list)-len(exception_list)
        msg = check_hint_msg.format(hint=our_hint, matched=match_count, solve=solved, unsolve=unsolve_list, exceptions=exception_list)
        print(msg)


def test_SingleODESolver():
    # Test that not implemented methods give NotImplementedError
    # Subclasses should override these methods.
    problem = SingleODEProblem(f(x).diff(x), f(x), x)
    solver = SingleODESolver(problem)
    raises(NotImplementedError, lambda: solver.matches())
    raises(NotImplementedError, lambda: solver.get_general_solution())
    raises(NotImplementedError, lambda: solver._matches())
    raises(NotImplementedError, lambda: solver._get_general_solution())

    # This ODE can not be solved by the FirstLinear solver. Here we test that
    # it does not match and the asking for a general solution gives
    # ODEMatchError

    problem = SingleODEProblem(f(x).diff(x) + f(x)*f(x), f(x), x)

    solver = FirstLinear(problem)
    raises(ODEMatchError, lambda: solver.get_general_solution())

    solver = FirstLinear(problem)
    assert solver.matches() is False

    #These are just test for order of ODE

    problem = SingleODEProblem(f(x).diff(x) + f(x), f(x), x)
    assert problem.order == 1

    problem = SingleODEProblem(f(x).diff(x,4) + f(x).diff(x,2) - f(x).diff(x,3), f(x), x)
    assert problem.order == 4


def test_separable_reduced():
    df = f(x).diff(x)
    eq = (x / f(x))*df  + tan(x**2*f(x) / (x**2*f(x) - 1))
    assert classify_ode(eq) == ('separable_reduced', 'lie_group',
        'separable_reduced_Integral')
    _ode_solver_test(_get_examples_ode_sol_separable_reduced)


@slow
def test_slow_examples_separable_reduced():
    _ode_solver_test(_get_examples_ode_sol_separable_reduced, run_slow_test=True)


def test_2nd_2F1_hypergeometric():
    _ode_solver_test(_get_examples_ode_sol_2nd_2F1_hypergeometric)


def test_2nd_2F1_hypergeometric_intrgral():
    eq = x*(x-1)*f(x).diff(x, 2) + (-1+ S(7)/2*x)*f(x).diff(x) + f(x)
    sol = Eq(f(x), (C1 + C2*Integral(exp(Integral((1 - x/2)/(x*(x - 1)), x))/(1 -
          x/2)**2, x))*exp(Integral(1/(x - 1), x)/4)*exp(-Integral(7/(x -
          1), x)/4)*hyper((S(1)/2, -1), (1,), x))
    assert sol == dsolve(eq, hint='2nd_hypergeometric_Integral')
    assert checkodesol(eq, sol) == (True, 0)


def test_2nd_linear_bessel_equation():
    _ode_solver_test(_get_examples_ode_sol_2nd_linear_bessel)


def test_nth_algebraic():
    eqn = f(x) + f(x)*f(x).diff(x)
    solns = [Eq(f(x), exp(x)),
             Eq(f(x), C1*exp(C2*x))]
    solns_final =  _remove_redundant_solutions(eqn, solns, 2, x)
    assert solns_final == [Eq(f(x), C1*exp(C2*x))]

    _ode_solver_test(_get_examples_ode_sol_nth_algebraic)


@slow
def test_slow_examples_nth_linear_constant_coeff_var_of_parameters():
    _ode_solver_test(_get_examples_ode_sol_nth_linear_var_of_parameters, run_slow_test=True)


def test_nth_linear_constant_coeff_var_of_parameters():
    _ode_solver_test(_get_examples_ode_sol_nth_linear_var_of_parameters)


@slow
def test_nth_linear_constant_coeff_variation_of_parameters__integral():
    # solve_variation_of_parameters shouldn't attempt to simplify the
    # Wronskian if simplify=False.  If wronskian() ever gets good enough
    # to simplify the result itself, this test might fail.
    our_hint = 'nth_linear_constant_coeff_variation_of_parameters_Integral'
    eq = f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x) - 2*x - exp(I*x)
    sol_simp = dsolve(eq, f(x), hint=our_hint, simplify=True)
    sol_nsimp = dsolve(eq, f(x), hint=our_hint, simplify=False)
    assert sol_simp != sol_nsimp
    assert checkodesol(eq, sol_simp, order=5, solve_for_func=False) == (True, 0)
    assert checkodesol(eq, sol_simp, order=5, solve_for_func=False) == (True, 0)


@slow
def test_slow_examples_1st_exact():
    _ode_solver_test(_get_examples_ode_sol_1st_exact, run_slow_test=True)


def test_1st_exact():
    _ode_solver_test(_get_examples_ode_sol_1st_exact)


def test_1st_exact_integral():
    eq = cos(f(x)) - (x*sin(f(x)) - f(x)**2)*f(x).diff(x)
    sol_1 = dsolve(eq, f(x), simplify=False, hint='1st_exact_Integral')
    assert checkodesol(eq, sol_1, order=1, solve_for_func=False)


@slow
def test_slow_examples_nth_order_reducible():
    _ode_solver_test(_get_examples_ode_sol_nth_order_reducible, run_slow_test=True)


@slow
def test_slow_examples_nth_linear_constant_coeff_undetermined_coefficients():
    _ode_solver_test(_get_examples_ode_sol_nth_linear_undetermined_coefficients, run_slow_test=True)


@slow
def test_slow_examples_separable():
    _ode_solver_test(_get_examples_ode_sol_separable, run_slow_test=True)


def test_nth_linear_constant_coeff_undetermined_coefficients():
    #issue-https://github.com/sympy/sympy/issues/5787
    # This test case is to show the classification of imaginary constants under
    # nth_linear_constant_coeff_undetermined_coefficients
    eq = Eq(diff(f(x), x), I*f(x) + S.Half - I)
    our_hint = 'nth_linear_constant_coeff_undetermined_coefficients'
    assert our_hint in classify_ode(eq)
    _ode_solver_test(_get_examples_ode_sol_nth_linear_undetermined_coefficients)


def test_nth_order_reducible():
    from sympy.solvers.ode.ode import _nth_order_reducible_match

    F = lambda eq: _nth_order_reducible_match(eq, f(x))
    D = Derivative
    assert F(D(y*f(x), x, y) + D(f(x), x)) is None
    assert F(D(y*f(y), y, y) + D(f(y), y)) is None
    assert F(f(x)*D(f(x), x) + D(f(x), x, 2)) is None
    assert F(D(x*f(y), y, 2) + D(u*y*f(x), x, 3)) is None  # no simplification by design
    assert F(D(f(y), y, 2) + D(f(y), y, 3) + D(f(x), x, 4)) is None
    assert F(D(f(x), x, 2) + D(f(x), x, 3)) == dict(n=2)

    _ode_solver_test(_get_examples_ode_sol_nth_order_reducible)


def test_separable():
    _ode_solver_test(_get_examples_ode_sol_separable)


def test_factorable():
    assert integrate(-asin(f(2*x)+pi), x) == -Integral(asin(pi + f(2*x)), x)
    _ode_solver_test(_get_examples_ode_sol_factorable)


def test_Riccati_special_minus2():
    _ode_solver_test(_get_examples_ode_sol_riccati)


def test_Bernoulli():
    _ode_solver_test(_get_examples_ode_sol_bernoulli)


def test_1st_linear():
    _ode_solver_test(_get_examples_ode_sol_1st_linear)


def test_almost_linear():
   _ode_solver_test(_get_examples_ode_sol_almost_linear)


def test_Liouville_ODE():
    hint = 'Liouville'
    not_Liouville1 = classify_ode(diff(f(x), x)/x + f(x)*diff(f(x), x, x)/2 -
        diff(f(x), x)**2/2, f(x))
    not_Liouville2 = classify_ode(diff(f(x), x)/x + diff(f(x), x, x)/2 -
        x*diff(f(x), x)**2/2, f(x))
    assert hint not in not_Liouville1
    assert hint not in not_Liouville2
    assert hint + '_Integral' not in not_Liouville1
    assert hint + '_Integral' not in not_Liouville2

    _ode_solver_test(_get_examples_ode_sol_liouville)


def test_nth_order_linear_euler_eq_homogeneous():
    x, t, a, b, c = symbols('x t a b c')
    y = Function('y')
    our_hint = "nth_linear_euler_eq_homogeneous"

    eq = diff(f(t), t, 4)*t**4 - 13*diff(f(t), t, 2)*t**2 + 36*f(t)
    assert our_hint in classify_ode(eq)

    eq = a*y(t) + b*t*diff(y(t), t) + c*t**2*diff(y(t), t, 2)
    assert our_hint in classify_ode(eq)

    _ode_solver_test(_get_examples_ode_sol_euler_homogeneous)


def test_nth_order_linear_euler_eq_nonhomogeneous_undetermined_coefficients():
    x, t = symbols('x t')
    a, b, c, d = symbols('a b c d', integer=True)
    our_hint = "nth_linear_euler_eq_nonhomogeneous_undetermined_coefficients"

    eq = x**4*diff(f(x), x, 4) - 13*x**2*diff(f(x), x, 2) + 36*f(x) + x
    assert our_hint in classify_ode(eq, f(x))

    eq = a*x**2*diff(f(x), x, 2) + b*x*diff(f(x), x) + c*f(x) + d*log(x)
    assert our_hint in classify_ode(eq, f(x))

    _ode_solver_test(_get_examples_ode_sol_euler_undetermined_coeff)


def test_nth_order_linear_euler_eq_nonhomogeneous_variation_of_parameters():
    x, t = symbols('x, t')
    a, b, c, d = symbols('a, b, c, d', integer=True)
    our_hint = "nth_linear_euler_eq_nonhomogeneous_variation_of_parameters"

    eq = Eq(x**2*diff(f(x),x,2) - 8*x*diff(f(x),x) + 12*f(x), x**2)
    assert our_hint in classify_ode(eq, f(x))

    eq = Eq(a*x**3*diff(f(x),x,3) + b*x**2*diff(f(x),x,2) + c*x*diff(f(x),x) + d*f(x), x*log(x))
    assert our_hint in classify_ode(eq, f(x))

    _ode_solver_test(_get_examples_ode_sol_euler_var_para)


@_add_example_keys
def _get_examples_ode_sol_euler_homogeneous():
    return {
            'hint': "nth_linear_euler_eq_homogeneous",
            'func': f(x),
            'examples':{
    'euler_hom_01': {
        'eq': Eq(-3*diff(f(x), x)*x + 2*x**2*diff(f(x), x, x), 0),
        'sol': [Eq(f(x), C1 + C2*x**Rational(5, 2))],
    },

    'euler_hom_02': {
        'eq': Eq(3*f(x) - 5*diff(f(x), x)*x + 2*x**2*diff(f(x), x, x), 0),
        'sol': [Eq(f(x), C1*sqrt(x) + C2*x**3)]
    },

    'euler_hom_03': {
        'eq': Eq(4*f(x) + 5*diff(f(x), x)*x + x**2*diff(f(x), x, x), 0),
        'sol': [Eq(f(x), (C1 + C2*log(x))/x**2)]
    },

    'euler_hom_04': {
        'eq': Eq(6*f(x) - 6*diff(f(x), x)*x + 1*x**2*diff(f(x), x, x) + x**3*diff(f(x), x, x, x), 0),
        'sol': [Eq(f(x), C1/x**2 + C2*x + C3*x**3)]
    },

    'euler_hom_05': {
        'eq': Eq(-125*f(x) + 61*diff(f(x), x)*x - 12*x**2*diff(f(x), x, x) + x**3*diff(f(x), x, x, x), 0),
        'sol': [Eq(f(x), x**5*(C1 + C2*log(x) + C3*log(x)**2))]
    },

    'euler_hom_06': {
        'eq': x**2*diff(f(x), x, 2) + x*diff(f(x), x) - 9*f(x),
        'sol': [Eq(f(x), C1*x**-3 + C2*x**3)]
    },

    'euler_hom_07': {
        'eq': sin(x)*x**2*f(x).diff(x, 2) + sin(x)*x*f(x).diff(x) + sin(x)*f(x),
        'sol': [Eq(f(x), C1*sin(log(x)) + C2*cos(log(x)))],
        'XFAIL': ['2nd_power_series_regular','nth_linear_euler_eq_nonhomogeneous_undetermined_coefficients']
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_euler_undetermined_coeff():
    return {
            'hint': "nth_linear_euler_eq_nonhomogeneous_undetermined_coefficients",
            'func': f(x),
            'examples':{
    'euler_undet_01': {
        'eq': Eq(x**2*diff(f(x), x, x) + x*diff(f(x), x), 1),
        'sol': [Eq(f(x), C1 + C2*log(x) + log(x)**2/2)]
    },

    'euler_undet_02': {
        'eq': Eq(x**2*diff(f(x), x, x) - 2*x*diff(f(x), x) + 2*f(x), x**3),
        'sol': [Eq(f(x), x*(C1 + C2*x + Rational(1, 2)*x**2))]
    },

    'euler_undet_03': {
        'eq': Eq(x**2*diff(f(x), x, x) - x*diff(f(x), x) - 3*f(x), log(x)/x),
        'sol': [Eq(f(x), (C1 + C2*x**4 - log(x)**2/8 - log(x)/16)/x)]
    },

    'euler_undet_04': {
        'eq': Eq(x**2*diff(f(x), x, x) + 3*x*diff(f(x), x) - 8*f(x), log(x)**3 - log(x)),
        'sol': [Eq(f(x), C1/x**4 + C2*x**2 - Rational(1,8)*log(x)**3 - Rational(3,32)*log(x)**2 - Rational(1,64)*log(x) - Rational(7, 256))]
    },

    'euler_undet_05': {
        'eq': Eq(x**3*diff(f(x), x, x, x) - 3*x**2*diff(f(x), x, x) + 6*x*diff(f(x), x) - 6*f(x), log(x)),
        'sol': [Eq(f(x), C1*x + C2*x**2 + C3*x**3 - Rational(1, 6)*log(x) - Rational(11, 36))]
    },

    #Below examples were added for the issue: https://github.com/sympy/sympy/issues/5096
    'euler_undet_06': {
        'eq': 2*x**2*f(x).diff(x, 2) + f(x) + sqrt(2*x)*sin(log(2*x)/2),
        'sol': [Eq(f(x), sqrt(x)*(C1*sin(log(x)/2) + C2*cos(log(x)/2) + sqrt(2)*log(x)*cos(log(2*x)/2)/2))]
    },

    'euler_undet_07': {
        'eq': 2*x**2*f(x).diff(x, 2) + f(x) + sin(log(2*x)/2),
        'sol': [Eq(f(x), C1*sqrt(x)*sin(log(x)/2) + C2*sqrt(x)*cos(log(x)/2) - 2*sin(log(2*x)/2)/5 - 4*cos(log(2*x)/2)/5)]
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_euler_var_para():
    return {
            'hint': "nth_linear_euler_eq_nonhomogeneous_variation_of_parameters",
            'func': f(x),
            'examples':{
    'euler_var_01': {
        'eq': Eq(x**2*Derivative(f(x), x, x) - 2*x*Derivative(f(x), x) + 2*f(x), x**4),
        'sol': [Eq(f(x), x*(C1 + C2*x + x**3/6))]
    },

    'euler_var_02': {
        'eq': Eq(3*x**2*diff(f(x), x, x) + 6*x*diff(f(x), x) - 6*f(x), x**3*exp(x)),
        'sol': [Eq(f(x), C1/x**2 + C2*x + x*exp(x)/3 - 4*exp(x)/3 + 8*exp(x)/(3*x) - 8*exp(x)/(3*x**2))]
    },

    'euler_var_03': {
        'eq': Eq(x**2*Derivative(f(x), x, x) - 2*x*Derivative(f(x), x) + 2*f(x), x**4*exp(x)),
        'sol':  [Eq(f(x), x*(C1 + C2*x + x*exp(x) - 2*exp(x)))]
    },

    'euler_var_04': {
        'eq': x**2*Derivative(f(x), x, x) - 2*x*Derivative(f(x), x) + 2*f(x) - log(x),
        'sol': [Eq(f(x), C1*x + C2*x**2 + log(x)/2 + Rational(3, 4))]
    },

    'euler_var_05': {
        'eq': -exp(x) + (x*Derivative(f(x), (x, 2)) + Derivative(f(x), x))/x,
        'sol': [Eq(f(x), C1 + C2*log(x) + exp(x) - Ei(x))]
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_bernoulli():
    # Type: Bernoulli, f'(x) + p(x)*f(x) == q(x)*f(x)**n
    return {
            'hint': "Bernoulli",
            'func': f(x),
            'examples':{
    'bernoulli_01': {
        'eq': Eq(x*f(x).diff(x) + f(x) - f(x)**2, 0),
        'sol': [Eq(f(x), 1/(C1*x + 1))],
        'XFAIL': ['separable_reduced']
    },

    'bernoulli_02': {
        'eq': f(x).diff(x) - y*f(x),
        'sol': [Eq(f(x), C1*exp(x*y))]
    },

    'bernoulli_03': {
        'eq': f(x)*f(x).diff(x) - 1,
        'sol': [Eq(f(x), -sqrt(C1 + 2*x)), Eq(f(x), sqrt(C1 + 2*x))]
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_riccati():
    # Type: Riccati special alpha = -2, a*dy/dx + b*y**2 + c*y/x +d/x**2
    return {
            'hint': "Riccati_special_minus2",
            'func': f(x),
            'examples':{
    'riccati_01': {
        'eq': 2*f(x).diff(x) + f(x)**2 - f(x)/x + 3*x**(-2),
        'sol': [Eq(f(x), (-sqrt(3)*tan(C1 + sqrt(3)*log(x)/4) + 3)/(2*x))],
    },
    },
    }


@_add_example_keys
def _get_examples_ode_sol_1st_linear():
    # Type: first order linear form f'(x)+p(x)f(x)=q(x)
    return {
            'hint': "1st_linear",
            'func': f(x),
            'examples':{
    'linear_01': {
        'eq': Eq(f(x).diff(x) + x*f(x), x**2),
        'sol': [Eq(f(x), (C1 + x*exp(x**2/2)- sqrt(2)*sqrt(pi)*erfi(sqrt(2)*x/2)/2)*exp(-x**2/2))],
    },
    },
    }


@_add_example_keys
def _get_examples_ode_sol_factorable():
    """ some hints are marked as xfail for examples because they missed additional algebraic solution
    which could be found by Factorable hint. Fact_01 raise exception for
    nth_linear_constant_coeff_undetermined_coefficients"""

    y = Dummy('y')
    a0,a1,a2,a3,a4 = symbols('a0, a1, a2, a3, a4')
    return {
            'hint': "factorable",
            'func': f(x),
            'examples':{
    'fact_01': {
        'eq': f(x) + f(x)*f(x).diff(x),
        'sol': [Eq(f(x), 0), Eq(f(x), C1 - x)],
        'XFAIL': ['separable', '1st_exact', '1st_linear', 'Bernoulli', '1st_homogeneous_coeff_best',
        '1st_homogeneous_coeff_subs_indep_div_dep', '1st_homogeneous_coeff_subs_dep_div_indep',
        'lie_group', 'nth_linear_euler_eq_nonhomogeneous_undetermined_coefficients',
        'nth_linear_constant_coeff_variation_of_parameters',
        'nth_linear_euler_eq_nonhomogeneous_variation_of_parameters',
        'nth_linear_constant_coeff_undetermined_coefficients']
    },

    'fact_02': {
        'eq': f(x)*(f(x).diff(x)+f(x)*x+2),
        'sol': [Eq(f(x), (C1 - sqrt(2)*sqrt(pi)*erfi(sqrt(2)*x/2))*exp(-x**2/2)), Eq(f(x), 0)],
        'XFAIL': ['Bernoulli', '1st_linear', 'lie_group']
    },

    'fact_03': {
        'eq': (f(x).diff(x)+f(x)*x**2)*(f(x).diff(x, 2) + x*f(x)),
        'sol':  [Eq(f(x), C1*airyai(-x) + C2*airybi(-x)),Eq(f(x), C1*exp(-x**3/3))]
    },

    'fact_04': {
        'eq': (f(x).diff(x)+f(x)*x**2)*(f(x).diff(x, 2) + f(x)),
        'sol': [Eq(f(x), C1*exp(-x**3/3)), Eq(f(x), C1*sin(x) + C2*cos(x))]
    },

    'fact_05': {
        'eq': (f(x).diff(x)**2-1)*(f(x).diff(x)**2-4),
        'sol': [Eq(f(x), C1 - x), Eq(f(x), C1 + x), Eq(f(x), C1 + 2*x), Eq(f(x), C1 - 2*x)]
    },

    'fact_06': {
        'eq': (f(x).diff(x, 2)-exp(f(x)))*f(x).diff(x),
        'sol': [Eq(f(x), C1)]
    },

    'fact_07': {
        'eq': (f(x).diff(x)**2-1)*(f(x)*f(x).diff(x)-1),
        'sol': [Eq(f(x), C1 - x), Eq(f(x), -sqrt(C1 + 2*x)),Eq(f(x), sqrt(C1 + 2*x)), Eq(f(x), C1 + x)]
    },

    'fact_08': {
        'eq': Derivative(f(x), x)**4 - 2*Derivative(f(x), x)**2 + 1,
        'sol': [Eq(f(x), C1 - x), Eq(f(x), C1 + x)]
    },

    'fact_09': {
        'eq': f(x)**2*Derivative(f(x), x)**6 - 2*f(x)**2*Derivative(f(x),
         x)**4 + f(x)**2*Derivative(f(x), x)**2 - 2*f(x)*Derivative(f(x),
         x)**5 + 4*f(x)*Derivative(f(x), x)**3 - 2*f(x)*Derivative(f(x),
         x) + Derivative(f(x), x)**4 - 2*Derivative(f(x), x)**2 + 1,
        'sol': [Eq(f(x), C1 - x), Eq(f(x), -sqrt(C1 + 2*x)),
           Eq(f(x), sqrt(C1 + 2*x)), Eq(f(x), C1 + x)]
    },

    'fact_10': {
        'eq': x**4*f(x)**2 + 2*x**4*f(x)*Derivative(f(x), (x, 2)) + x**4*Derivative(f(x),
         (x, 2))**2  + 2*x**3*f(x)*Derivative(f(x), x) + 2*x**3*Derivative(f(x),
         x)*Derivative(f(x), (x, 2)) - 7*x**2*f(x)**2 - 7*x**2*f(x)*Derivative(f(x),
         (x, 2)) + x**2*Derivative(f(x), x)**2 - 7*x*f(x)*Derivative(f(x), x) + 12*f(x)**2,
        'sol': [Eq(f(x), C1*besselj(2, x) + C2*bessely(2, x)), Eq(f(x), C1*besselj(sqrt(3),
           x) + C2*bessely(sqrt(3), x))]
    },

    'fact_11': {
        'eq': (f(x).diff(x, 2)-exp(f(x)))*(f(x).diff(x, 2)+exp(f(x))),
        'sol': [], #currently dsolve doesn't return any solution for this example
        'XFAIL': ['factorable']
    },

    #Below examples were added for the issue: https://github.com/sympy/sympy/issues/15889
    'fact_12': {
        'eq': exp(f(x).diff(x))-f(x)**2,
        'sol': [Eq(NonElementaryIntegral(1/log(y**2), (y, f(x))), C1 + x)],
        'XFAIL': ['lie_group'] #It shows not implemented error for lie_group.
    },

    'fact_13': {
        'eq': f(x).diff(x)**2 - f(x)**3,
        'sol': [Eq(f(x), 4/(C1**2 - 2*C1*x + x**2))],
        'XFAIL': ['lie_group'] #It shows not implemented error for lie_group.
    },

    'fact_14': {
        'eq': f(x).diff(x)**2 - f(x),
        'sol': [Eq(f(x), C1**2/4 - C1*x/2 + x**2/4)]
    },

    'fact_15': {
        'eq': f(x).diff(x)**2 - f(x)**2,
        'sol': [Eq(f(x), C1*exp(x)), Eq(f(x), C1*exp(-x))]
    },

    'fact_16': {
        'eq': f(x).diff(x)**2 - f(x)**3,
        'sol': [Eq(f(x), 4/(C1**2 - 2*C1*x + x**2))]
    },

    # kamke ode 1.1
    'fact_17': {
        'eq': f(x).diff(x)-(a4*x**4 + a3*x**3 + a2*x**2 + a1*x + a0)**(-1/2),
        'sol': [Eq(f(x), C1 + Integral(1/sqrt(a0 + a1*x + a2*x**2 + a3*x**3 + a4*x**4), x))]
    },

    # This is from issue: https://github.com/sympy/sympy/issues/9446
    'fact_18':{
        'eq': Eq(f(2 * x), sin(Derivative(f(x)))),
        'sol': [Eq(f(x), C1 + pi*x - Integral(asin(f(2*x)), x)), Eq(f(x), C1 + Integral(asin(f(2*x)), x))],
        'checkodesol_XFAIL':True
    },
    }
    }



@_add_example_keys
def _get_examples_ode_sol_almost_linear():
    from sympy import Ei
    A = Symbol('A', positive=True)
    f = Function('f')
    d = f(x).diff(x)

    return {
            'hint': "almost_linear",
            'func': f(x),
            'examples':{
    'almost_lin_01': {
        'eq': x**2*f(x)**2*d + f(x)**3 + 1,
        'sol': [Eq(f(x), (C1*exp(3/x) - 1)**Rational(1, 3)),
        Eq(f(x), (-1 - sqrt(3)*I)*(C1*exp(3/x) - 1)**Rational(1, 3)/2),
        Eq(f(x), (-1 + sqrt(3)*I)*(C1*exp(3/x) - 1)**Rational(1, 3)/2)],

    },

    'almost_lin_02': {
        'eq': x*f(x)*d + 2*x*f(x)**2 + 1,
        'sol': [Eq(f(x), -sqrt((C1 - 2*Ei(4*x))*exp(-4*x))), Eq(f(x), sqrt((C1 - 2*Ei(4*x))*exp(-4*x)))]
    },

    'almost_lin_03': {
        'eq':  x*d + x*f(x) + 1,
        'sol': [Eq(f(x), (C1 - Ei(x))*exp(-x))]
    },

    'almost_lin_04': {
        'eq': x*exp(f(x))*d + exp(f(x)) + 3*x,
        'sol': [Eq(f(x), log(C1/x - x*Rational(3, 2)))],
    },

    'almost_lin_05': {
        'eq': x + A*(x + diff(f(x), x) + f(x)) + diff(f(x), x) + f(x) + 2,
        'sol': [Eq(f(x), (C1 + Piecewise(
        (x, Eq(A + 1, 0)), ((-A*x + A - x - 1)*exp(x)/(A + 1), True)))*exp(-x))],
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_liouville():
    return {
            'hint': "Liouville",
            'func': f(x),
            'examples':{
    'liouville_01': {
        'eq': diff(f(x), x)/x + diff(f(x), x, x)/2 - diff(f(x), x)**2/2,
        'sol': [Eq(f(x), log(x/(C1 + C2*x)))],

    },

    'liouville_02': {
        'eq': diff(x*exp(-f(x)), x, x),
        'sol': [Eq(f(x), log(x/(C1 + C2*x)))]
    },

    'liouville_03': {
        'eq':  ((diff(f(x), x)/x + diff(f(x), x, x)/2 - diff(f(x), x)**2/2)*exp(-f(x))/exp(f(x))).expand(),
        'sol': [Eq(f(x), log(x/(C1 + C2*x)))]
    },

    'liouville_04': {
        'eq': diff(f(x), x, x) + 1/f(x)*(diff(f(x), x))**2 + 1/x*diff(f(x), x),
        'sol': [Eq(f(x), -sqrt(C1 + C2*log(x))), Eq(f(x), sqrt(C1 + C2*log(x)))],
    },

    'liouville_05': {
        'eq': x*diff(f(x), x, x) + x/f(x)*diff(f(x), x)**2 + x*diff(f(x), x),
        'sol': [Eq(f(x), -sqrt(C1 + C2*exp(-x))), Eq(f(x), sqrt(C1 + C2*exp(-x)))],
    },

    'liouville_06': {
        'eq': Eq((x*exp(f(x))).diff(x, x), 0),
        'sol': [Eq(f(x), log(C1 + C2/x))],
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_nth_algebraic():
    M, m, r, t = symbols('M m r t')
    phi = Function('phi')
    # This one needs a substitution f' = g.
    # 'algeb_12': {
    #     'eq': -exp(x) + (x*Derivative(f(x), (x, 2)) + Derivative(f(x), x))/x,
    #     'sol': [Eq(f(x), C1 + C2*log(x) + exp(x) - Ei(x))],
    # },
    return {
            'hint': "nth_algebraic",
            'func': f(x),
            'examples':{
    'algeb_01': {
        'eq': f(x) * f(x).diff(x) * f(x).diff(x, x) * (f(x) - 1) * (f(x).diff(x) - x),
        'sol': [Eq(f(x), C1 + x**2/2), Eq(f(x), C1 + C2*x)]
    },

    'algeb_02': {
        'eq': f(x) * f(x).diff(x) * f(x).diff(x, x) * (f(x) - 1),
        'sol': [Eq(f(x), C1 + C2*x)]
    },

    'algeb_03': {
        'eq': f(x) * f(x).diff(x) * f(x).diff(x, x),
        'sol': [Eq(f(x), C1 + C2*x)]
    },

    'algeb_04': {
        'eq': Eq(-M * phi(t).diff(t),
         Rational(3, 2) * m * r**2 * phi(t).diff(t) * phi(t).diff(t,t)),
        'sol': [Eq(phi(t), C1), Eq(phi(t), C1 + C2*t - M*t**2/(3*m*r**2))],
        'func': phi(t)
    },

    'algeb_05': {
        'eq': (1 - sin(f(x))) * f(x).diff(x),
        'sol': [Eq(f(x), C1)],
        'XFAIL': ['separable']  #It raised exception.
    },

    'algeb_06': {
        'eq': (diff(f(x)) - x)*(diff(f(x)) + x),
        'sol': [Eq(f(x), C1 - x**2/2), Eq(f(x), C1 + x**2/2)]
    },

    'algeb_07': {
        'eq': Eq(Derivative(f(x), x), Derivative(g(x), x)),
        'sol': [Eq(f(x), C1 + g(x))],
    },

    'algeb_08': {
        'eq': f(x).diff(x) - C1,   #this example is from issue 15999
        'sol': [Eq(f(x), C1*x + C2)],
    },

    'algeb_09': {
        'eq': f(x)*f(x).diff(x),
        'sol': [Eq(f(x), C1)],
    },

    'algeb_10': {
        'eq': (diff(f(x)) - x)*(diff(f(x)) + x),
        'sol': [Eq(f(x), C1 - x**2/2), Eq(f(x), C1 + x**2/2)],
    },

    'algeb_11': {
        'eq': f(x) + f(x)*f(x).diff(x),
        'sol': [Eq(f(x), 0), Eq(f(x), C1 - x)],
        'XFAIL': ['separable', '1st_exact', '1st_linear', 'Bernoulli', '1st_homogeneous_coeff_best',
         '1st_homogeneous_coeff_subs_indep_div_dep', '1st_homogeneous_coeff_subs_dep_div_indep',
         'lie_group', 'nth_linear_constant_coeff_undetermined_coefficients',
         'nth_linear_euler_eq_nonhomogeneous_undetermined_coefficients',
         'nth_linear_constant_coeff_variation_of_parameters',
         'nth_linear_euler_eq_nonhomogeneous_variation_of_parameters']
         #nth_linear_constant_coeff_undetermined_coefficients raises exception rest all of them misses a solution.
    },

    'algeb_12': {
        'eq': Derivative(x*f(x), x, x, x),
        'sol': [Eq(f(x), (C1 + C2*x + C3*x**2) / x)],
        'XFAIL': ['nth_algebraic']  # It passes only when prep=False is set in dsolve.
    },

    'algeb_13': {
        'eq': Eq(Derivative(x*Derivative(f(x), x), x)/x, exp(x)),
        'sol': [Eq(f(x), C1 + C2*log(x) + exp(x) - Ei(x))],
        'XFAIL': ['nth_algebraic']  # It passes only when prep=False is set in dsolve.
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_nth_order_reducible():
    return {
            'hint': "nth_order_reducible",
            'func': f(x),
            'examples':{
    'reducible_01': {
        'eq': Eq(x*Derivative(f(x), x)**2 + Derivative(f(x), x, 2), 0),
        'sol': [Eq(f(x),C1 - sqrt(-1/C2)*log(-C2*sqrt(-1/C2) + x) +
        sqrt(-1/C2)*log(C2*sqrt(-1/C2) + x))],
        'slow': True,
    },

    'reducible_02': {
        'eq': -exp(x) + (x*Derivative(f(x), (x, 2)) + Derivative(f(x), x))/x,
        'sol': [Eq(f(x), C1 + C2*log(x) + exp(x) - Ei(x))],
        'slow': True,
    },

    'reducible_03': {
        'eq': Eq(sqrt(2) * f(x).diff(x,x,x) + f(x).diff(x), 0),
        'sol': [Eq(f(x), C1 + C2*sin(2**Rational(3, 4)*x/2) + C3*cos(2**Rational(3, 4)*x/2))],
        'slow': True,
    },

    'reducible_04': {
        'eq': f(x).diff(x, 2) + 2*f(x).diff(x),
        'sol': [Eq(f(x), C1 + C2*exp(-2*x))],
    },

    'reducible_05': {
        'eq': f(x).diff(x, 3) + f(x).diff(x, 2) - 6*f(x).diff(x),
        'sol': [Eq(f(x), C1 + C2*exp(-3*x) + C3*exp(2*x))],
        'slow': True,
    },

    'reducible_06': {
        'eq': f(x).diff(x, 4) - f(x).diff(x, 3) - 4*f(x).diff(x, 2) + \
        4*f(x).diff(x),
        'sol': [Eq(f(x), C1 + C2*exp(-2*x) + C3*exp(x) + C4*exp(2*x))],
        'slow': True,
    },

    'reducible_07': {
        'eq': f(x).diff(x, 4) + 3*f(x).diff(x, 3),
        'sol': [Eq(f(x), C1 + C2*x + C3*x**2 + C4*exp(-3*x))],
        'slow': True,
    },

    'reducible_08': {
        'eq': f(x).diff(x, 4) - 2*f(x).diff(x, 2),
        'sol': [Eq(f(x), C1 + C2*x + C3*exp(-sqrt(2)*x) + C4*exp(sqrt(2)*x))],
        'slow': True,
    },

    'reducible_09': {
        'eq': f(x).diff(x, 4) + 4*f(x).diff(x, 2),
        'sol': [Eq(f(x), C1 + C2*x + C3*sin(2*x) + C4*cos(2*x))],
        'slow': True,
    },

    'reducible_10': {
        'eq': f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x),
        'sol': [Eq(f(x), C1 + C2*(x*sin(x) + cos(x)) + C3*(-x*cos(x) + sin(x)) + C4*sin(x) + C5*cos(x))],
        'slow': True,
    },

    'reducible_11': {
        'eq': f(x).diff(x, 2) - f(x).diff(x)**3,
        'sol': [Eq(f(x), C1 - sqrt(2)*(I*C2 + I*x)*sqrt(1/(C2 + x))),
        Eq(f(x), C1 + sqrt(2)*(I*C2 + I*x)*sqrt(1/(C2 + x)))],
        'slow': True,
    },
    }
    }



@_add_example_keys
def _get_examples_ode_sol_nth_linear_undetermined_coefficients():
    # examples 3-27 below are from Ordinary Differential Equations,
    #                     Tenenbaum and Pollard, pg. 231
    g = exp(-x)
    f2 = f(x).diff(x, 2)
    c = 3*f(x).diff(x, 3) + 5*f2 + f(x).diff(x) - f(x) - x
    return {
            'hint': "nth_linear_constant_coeff_undetermined_coefficients",
            'func': f(x),
            'examples':{
    'undet_01': {
        'eq': c - x*g,
        'sol': [Eq(f(x), C3*exp(x/3) - x + (C1 + x*(C2 - x**2/24 - 3*x/32))*exp(-x) - 1)],
        'slow': True,
    },

    'undet_02': {
        'eq': c - g,
        'sol': [Eq(f(x), C3*exp(x/3) - x + (C1 + x*(C2 - x/8))*exp(-x) - 1)],
        'slow': True,
    },

    'undet_03': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - 4,
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + 2)],
        'slow': True,
    },

    'undet_04': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - 12*exp(x),
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + 2*exp(x))],
        'slow': True,
    },

    'undet_05': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - exp(I*x),
        'sol': [Eq(f(x), (S(3)/10 + I/10)*(C1*exp(-2*x) + C2*exp(-x) - I*exp(I*x)))],
        'slow': True,
    },

    'undet_06': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - sin(x),
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + sin(x)/10 - 3*cos(x)/10)],
        'slow': True,
    },

    'undet_07': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - cos(x),
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + 3*sin(x)/10 + cos(x)/10)],
        'slow': True,
    },

    'undet_08': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - (8 + 6*exp(x) + 2*sin(x)),
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + exp(x) + sin(x)/5 - 3*cos(x)/5 + 4)],
        'slow': True,
    },

    'undet_09': {
        'eq': f2 + f(x).diff(x) + f(x) - x**2,
        'sol': [Eq(f(x), -2*x + x**2 + (C1*sin(x*sqrt(3)/2) + C2*cos(x*sqrt(3)/2))*exp(-x/2))],
        'slow': True,
    },

    'undet_10': {
        'eq': f2 - 2*f(x).diff(x) - 8*f(x) - 9*x*exp(x) - 10*exp(-x),
        'sol': [Eq(f(x), -x*exp(x) - 2*exp(-x) + C1*exp(-2*x) + C2*exp(4*x))],
        'slow': True,
    },

    'undet_11': {
        'eq': f2 - 3*f(x).diff(x) - 2*exp(2*x)*sin(x),
        'sol': [Eq(f(x), C1 + C2*exp(3*x) - 3*exp(2*x)*sin(x)/5 - exp(2*x)*cos(x)/5)],
        'slow': True,
    },

    'undet_12': {
        'eq': f(x).diff(x, 4) - 2*f2 + f(x) - x + sin(x),
        'sol': [Eq(f(x), x - sin(x)/4 + (C1 + C2*x)*exp(-x) + (C3 + C4*x)*exp(x))],
        'slow': True,
    },

    'undet_13': {
        'eq': f2 + f(x).diff(x) - x**2 - 2*x,
        'sol': [Eq(f(x), C1 + x**3/3 + C2*exp(-x))],
        'slow': True,
    },

    'undet_14': {
        'eq': f2 + f(x).diff(x) - x - sin(2*x),
        'sol': [Eq(f(x), C1 - x - sin(2*x)/5 - cos(2*x)/10 + x**2/2 + C2*exp(-x))],
        'slow': True,
    },

    'undet_15': {
        'eq': f2 + f(x) - 4*x*sin(x),
        'sol': [Eq(f(x), (C1 - x**2)*cos(x) + (C2 + x)*sin(x))],
        'slow': True,
    },

    'undet_16': {
        'eq': f2 + 4*f(x) - x*sin(2*x),
        'sol': [Eq(f(x), (C1 - x**2/8)*cos(2*x) + (C2 + x/16)*sin(2*x))],
        'slow': True,
    },

    'undet_17': {
        'eq': f2 + 2*f(x).diff(x) + f(x) - x**2*exp(-x),
        'sol': [Eq(f(x), (C1 + x*(C2 + x**3/12))*exp(-x))],
        'slow': True,
    },

    'undet_18': {
        'eq': f(x).diff(x, 3) + 3*f2 + 3*f(x).diff(x) + f(x) - 2*exp(-x) + \
        x**2*exp(-x),
        'sol': [Eq(f(x), (C1 + x*(C2 + x*(C3 - x**3/60 + x/3)))*exp(-x))],
        'slow': True,
    },

    'undet_19': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - exp(-2*x) - x**2,
        'sol': [Eq(f(x), C2*exp(-x) + x**2/2 - x*Rational(3,2) + (C1 - x)*exp(-2*x) + Rational(7,4))],
        'slow': True,
    },

    'undet_20': {
        'eq': f2 - 3*f(x).diff(x) + 2*f(x) - x*exp(-x),
        'sol': [Eq(f(x), C1*exp(x) + C2*exp(2*x) + (6*x + 5)*exp(-x)/36)],
        'slow': True,
    },

    'undet_21': {
        'eq': f2 + f(x).diff(x) - 6*f(x) - x - exp(2*x),
        'sol': [Eq(f(x), Rational(-1, 36) - x/6 + C2*exp(-3*x) + (C1 + x/5)*exp(2*x))],
        'slow': True,
    },

    'undet_22': {
        'eq': f2 + f(x) - sin(x) - exp(-x),
        'sol': [Eq(f(x), C2*sin(x) + (C1 - x/2)*cos(x) + exp(-x)/2)],
        'slow': True,
    },

    'undet_23': {
        'eq': f(x).diff(x, 3) - 3*f2 + 3*f(x).diff(x) - f(x) - exp(x),
        'sol': [Eq(f(x), (C1 + x*(C2 + x*(C3 + x/6)))*exp(x))],
        'slow': True,
    },

    'undet_24': {
        'eq': f2 + f(x) - S.Half - cos(2*x)/2,
        'sol': [Eq(f(x), S.Half - cos(2*x)/6 + C1*sin(x) + C2*cos(x))],
        'slow': True,
    },

    'undet_25': {
        'eq': f(x).diff(x, 3) - f(x).diff(x) - exp(2*x)*(S.Half - cos(2*x)/2),
        'sol': [Eq(f(x), C1 + C2*exp(-x) + C3*exp(x) + (-21*sin(2*x) + 27*cos(2*x) + 130)*exp(2*x)/1560)],
        'slow': True,
    },

    #Note: 'undet_26' is referred in 'undet_37'
    'undet_26': {
        'eq': (f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x) - 2*x -
        sin(x) - cos(x)),
        'sol': [Eq(f(x), C1 + x**2 + (C2 + x*(C3 - x/8))*sin(x) + (C4 + x*(C5 + x/8))*cos(x))],
        'slow': True,
    },

    'undet_27': {
        'eq': f2 + f(x) - cos(x)/2 + cos(3*x)/2,
        'sol': [Eq(f(x), cos(3*x)/16 + C2*cos(x) + (C1 + x/4)*sin(x))],
        'slow': True,
    },

    'undet_28': {
        'eq': f(x).diff(x) - 1,
        'sol': [Eq(f(x), C1 + x)],
        'slow': True,
    },

    # https://github.com/sympy/sympy/issues/19358
    'undet_29': {
        'eq': f2 + f(x).diff(x) + exp(x-C1),
        'sol': [Eq(f(x), C2 + C3*exp(-x) - exp(-C1 + x)/2)],
        'slow': True,
    },

    # https://github.com/sympy/sympy/issues/18408
    'undet_30': {
        'eq': f(x).diff(x, 3) - f(x).diff(x) - sinh(x),
        'sol': [Eq(f(x), C1 + C2*exp(-x) + C3*exp(x) + x*sinh(x)/2)],
    },

    'undet_31': {
        'eq': f(x).diff(x, 2) - 49*f(x) - sinh(3*x),
        'sol': [Eq(f(x), C1*exp(-7*x) + C2*exp(7*x) - sinh(3*x)/40)],
    },

    'undet_32': {
        'eq': f(x).diff(x, 3) - f(x).diff(x) - sinh(x) - exp(x),
        'sol': [Eq(f(x), C1 + C3*exp(-x) + x*sinh(x)/2 + (C2 + x/2)*exp(x))],
    },

    # https://github.com/sympy/sympy/issues/5096
    'undet_33': {
        'eq': f(x).diff(x, x) + f(x) - x*sin(x - 2),
        'sol': [Eq(f(x), C1*sin(x) + C2*cos(x) - x**2*cos(x - 2)/4 + x*sin(x - 2)/4)],
    },

    'undet_34': {
        'eq': f(x).diff(x, 2) + f(x) - x**4*sin(x-1),
        'sol': [ Eq(f(x), C1*sin(x) + C2*cos(x) - x**5*cos(x - 1)/10 + x**4*sin(x - 1)/4 + x**3*cos(x - 1)/2 - 3*x**2*sin(x - 1)/4 - 3*x*cos(x - 1)/4)],
    },

    'undet_35': {
        'eq': f(x).diff(x, 2) - f(x) - exp(x - 1),
        'sol': [Eq(f(x), C2*exp(-x) + (C1 + x*exp(-1)/2)*exp(x))],
    },

    'undet_36': {
        'eq': f(x).diff(x, 2)+f(x)-(sin(x-2)+1),
        'sol': [Eq(f(x), C1*sin(x) + C2*cos(x) - x*cos(x - 2)/2 + 1)],
    },

    # Equivalent to example_name 'undet_26'.
    # This previously failed because the algorithm for undetermined coefficients
    # didn't know to multiply exp(I*x) by sufficient x because it is linearly
    # dependent on sin(x) and cos(x).
    'undet_37': {
        'eq': f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x) - 2*x - exp(I*x),
        'sol': [Eq(f(x), C1 + x**2*(I*exp(I*x)/8 + 1) + (C2 + C3*x)*sin(x) + (C4 + C5*x)*cos(x))],
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_separable():
    # test_separable1-5 are from Ordinary Differential Equations, Tenenbaum and
    # Pollard, pg. 55
    a = Symbol('a')
    return {
            'hint': "separable",
            'func': f(x),
            'examples':{
    'separable_01': {
        'eq': f(x).diff(x) - f(x),
        'sol': [Eq(f(x), C1*exp(x))],
    },

    'separable_02': {
        'eq': x*f(x).diff(x) - f(x),
        'sol': [Eq(f(x), C1*x)],
    },

    'separable_03': {
        'eq': f(x).diff(x) + sin(x),
        'sol': [Eq(f(x), C1 + cos(x))],
    },

    'separable_04': {
        'eq': f(x)**2 + 1 - (x**2 + 1)*f(x).diff(x),
        'sol': [Eq(f(x), tan(C1 + atan(x)))],
    },

    'separable_05': {
        'eq': f(x).diff(x)/tan(x) - f(x) - 2,
        'sol': [Eq(f(x), C1/cos(x) - 2)],
    },

    'separable_06': {
        'eq': f(x).diff(x) * (1 - sin(f(x))) - 1,
        'sol': [Eq(-x + f(x) + cos(f(x)), C1)],
    },

    'separable_07': {
        'eq': f(x)*x**2*f(x).diff(x) - f(x)**3 - 2*x**2*f(x).diff(x),
        'sol': [Eq(f(x), (-x + sqrt(x*(4*C1*x + x - 4)))/(C1*x - 1)/2),
        Eq(f(x), -((x + sqrt(x*(4*C1*x + x - 4)))/(C1*x - 1))/2)],
        'slow': True,
    },

    'separable_08': {
        'eq': f(x)**2 - 1 - (2*f(x) + x*f(x))*f(x).diff(x),
        'sol': [Eq(f(x), -sqrt(C1*x**2 + 4*C1*x + 4*C1 + 1)),
        Eq(f(x), sqrt(C1*x**2 + 4*C1*x + 4*C1 + 1))],
        'slow': True,
    },

    'separable_09': {
        'eq': x*log(x)*f(x).diff(x) + sqrt(1 + f(x)**2),
        'sol': [Eq(f(x), sinh(C1 - log(log(x))))],  #One more solution is f(x)=I
        'slow': True,
        'checkodesol_XFAIL': True,
    },

    'separable_10': {
        'eq': exp(x + 1)*tan(f(x)) + cos(f(x))*f(x).diff(x),
        'sol': [Eq(E*exp(x) + log(cos(f(x)) - 1)/2 - log(cos(f(x)) + 1)/2 + cos(f(x)), C1)],
        'slow': True,
    },

    'separable_11': {
        'eq': (x*cos(f(x)) + x**2*sin(f(x))*f(x).diff(x) - a**2*sin(f(x))*f(x).diff(x)),
        'sol': [Eq(f(x), -acos(C1*sqrt(-a**2 + x**2)) + 2*pi),
        Eq(f(x), acos(C1*sqrt(-a**2 + x**2)))],
        'slow': True,
    },

    'separable_12': {
        'eq': f(x).diff(x) - f(x)*tan(x),
        'sol': [Eq(f(x), C1/cos(x))],
    },

    'separable_13': {
        'eq': (x - 1)*cos(f(x))*f(x).diff(x) - 2*x*sin(f(x)),
        'sol': [Eq(f(x), pi - asin(C1*(x**2 - 2*x + 1)*exp(2*x))),
        Eq(f(x), asin(C1*(x**2 - 2*x + 1)*exp(2*x)))],
    },

    'separable_14': {
        'eq': f(x).diff(x) - f(x)*log(f(x))/tan(x),
        'sol': [Eq(f(x), exp(C1*sin(x)))],
    },

    'separable_15': {
        'eq': x*f(x).diff(x) + (1 + f(x)**2)*atan(f(x)),
        'sol': [Eq(f(x), tan(C1/x))],  #Two more solutions are f(x)=0 and f(x)=I
        'slow': True,
        'checkodesol_XFAIL': True,
    },

    'separable_16': {
        'eq': f(x).diff(x) + x*(f(x) + 1),
        'sol': [Eq(f(x), -1 + C1*exp(-x**2/2))],
    },

    'separable_17': {
        'eq': exp(f(x)**2)*(x**2 + 2*x + 1) + (x*f(x) + f(x))*f(x).diff(x),
        'sol': [Eq(f(x), -sqrt(log(1/(C1 + x**2 + 2*x)))),
        Eq(f(x), sqrt(log(1/(C1 + x**2 + 2*x))))],
    },

    'separable_18': {
        'eq': f(x).diff(x) + f(x),
        'sol': [Eq(f(x), C1*exp(-x))],
    },

    'separable_19': {
        'eq': sin(x)*cos(2*f(x)) + cos(x)*sin(2*f(x))*f(x).diff(x),
        'sol': [Eq(f(x), pi - acos(C1/cos(x)**2)/2), Eq(f(x), acos(C1/cos(x)**2)/2)],
    },

    'separable_20': {
        'eq': (1 - x)*f(x).diff(x) - x*(f(x) + 1),
        'sol': [Eq(f(x), (C1*exp(-x) - x + 1)/(x - 1))],
    },

    'separable_21': {
        'eq': f(x)*diff(f(x), x) + x - 3*x*f(x)**2,
        'sol': [Eq(f(x), -sqrt(3)*sqrt(C1*exp(3*x**2) + 1)/3),
        Eq(f(x), sqrt(3)*sqrt(C1*exp(3*x**2) + 1)/3)],
    },

    'separable_22': {
        'eq': f(x).diff(x) - exp(x + f(x)),
        'sol': [Eq(f(x), log(-1/(C1 + exp(x))))],
        'XFAIL': ['lie_group'] #It shows 'NoneType' object is not subscriptable for lie_group.
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_1st_exact():
    # Type: Exact differential equation, p(x,f) + q(x,f)*f' == 0,
    # where dp/df == dq/dx
    '''
    Example 7 is an exact equation that fails under the exact engine. It is caught
    by first order homogeneous albeit with a much contorted solution.  The
    exact engine fails because of a poorly simplified integral of q(0,y)dy,
    where q is the function multiplying f'.  The solutions should be
    Eq(sqrt(x**2+f(x)**2)**3+y**3, C1).  The equation below is
    equivalent, but it is so complex that checkodesol fails, and takes a long
    time to do so.
    '''
    return {
            'hint': "1st_exact",
            'func': f(x),
            'examples':{
    '1st_exact_01': {
        'eq': sin(x)*cos(f(x)) + cos(x)*sin(f(x))*f(x).diff(x),
        'sol': [Eq(f(x), -acos(C1/cos(x)) + 2*pi), Eq(f(x), acos(C1/cos(x)))],
        'slow': True,
    },

    '1st_exact_02': {
        'eq': (2*x*f(x) + 1)/f(x) + (f(x) - x)/f(x)**2*f(x).diff(x),
        'sol': [Eq(f(x), exp(C1 - x**2 + LambertW(-x*exp(-C1 + x**2))))],
        'XFAIL': ['lie_group'], #It shows dsolve raises an exception: List index out of range for lie_group
        'slow': True,
        'checkodesol_XFAIL':True
    },

    '1st_exact_03': {
        'eq': 2*x + f(x)*cos(x) + (2*f(x) + sin(x) - sin(f(x)))*f(x).diff(x),
        'sol': [Eq(f(x)*sin(x) + cos(f(x)) + x**2 + f(x)**2, C1)],
        'XFAIL': ['lie_group'], #It goes into infinite loop for lie_group.
        'slow': True,
    },

    '1st_exact_04': {
        'eq': cos(f(x)) - (x*sin(f(x)) - f(x)**2)*f(x).diff(x),
        'sol': [Eq(x*cos(f(x)) + f(x)**3/3, C1)],
        'slow': True,
    },

    '1st_exact_05': {
        'eq': 2*x*f(x) + (x**2 + f(x)**2)*f(x).diff(x),
        'sol': [Eq(x**2*f(x) + f(x)**3/3, C1)],
        'slow': True,
        'simplify_flag':False
    },

    # This was from issue: https://github.com/sympy/sympy/issues/11290
    '1st_exact_06': {
        'eq': cos(f(x)) - (x*sin(f(x)) - f(x)**2)*f(x).diff(x),
        'sol': [Eq(x*cos(f(x)) + f(x)**3/3, C1)],
        'simplify_flag':False
    },

    '1st_exact_07': {
        'eq': x*sqrt(x**2 + f(x)**2) - (x**2*f(x)/(f(x) - sqrt(x**2 + f(x)**2)))*f(x).diff(x),
        'sol': [Eq(log(x),
        C1 - 9*sqrt(1 + f(x)**2/x**2)*asinh(f(x)/x)/(-27*f(x)/x +
        27*sqrt(1 + f(x)**2/x**2)) - 9*sqrt(1 + f(x)**2/x**2)*
        log(1 - sqrt(1 + f(x)**2/x**2)*f(x)/x + 2*f(x)**2/x**2)/
        (-27*f(x)/x + 27*sqrt(1 + f(x)**2/x**2)) +
        9*asinh(f(x)/x)*f(x)/(x*(-27*f(x)/x + 27*sqrt(1 + f(x)**2/x**2))) +
        9*f(x)*log(1 - sqrt(1 + f(x)**2/x**2)*f(x)/x + 2*f(x)**2/x**2)/
        (x*(-27*f(x)/x + 27*sqrt(1 + f(x)**2/x**2))))],
        'slow': True,
        'dsolve_too_slow':True
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_nth_linear_var_of_parameters():
    g = exp(-x)
    f2 = f(x).diff(x, 2)
    c = 3*f(x).diff(x, 3) + 5*f2 + f(x).diff(x) - f(x) - x
    return {
            'hint': "nth_linear_constant_coeff_variation_of_parameters",
            'func': f(x),
            'examples':{
    'var_of_parameters_01': {
        'eq': c - x*g,
        'sol': [Eq(f(x), C3*exp(x/3) - x + (C1 + x*(C2 - x**2/24 - 3*x/32))*exp(-x) - 1)],
        'slow': True,
    },

    'var_of_parameters_02': {
        'eq': c - g,
        'sol': [Eq(f(x), C3*exp(x/3) - x + (C1 + x*(C2 - x/8))*exp(-x) - 1)],
        'slow': True,
    },

    'var_of_parameters_03': {
        'eq': f(x).diff(x) - 1,
        'sol': [Eq(f(x), C1 + x)],
        'slow': True,
    },

    'var_of_parameters_04': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - 4,
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + 2)],
        'slow': True,
    },

    'var_of_parameters_05': {
        'eq': f2 + 3*f(x).diff(x) + 2*f(x) - 12*exp(x),
        'sol': [Eq(f(x), C1*exp(-2*x) + C2*exp(-x) + 2*exp(x))],
        'slow': True,
    },

    'var_of_parameters_06': {
        'eq': f2 - 2*f(x).diff(x) - 8*f(x) - 9*x*exp(x) - 10*exp(-x),
        'sol': [Eq(f(x), -x*exp(x) - 2*exp(-x) + C1*exp(-2*x) + C2*exp(4*x))],
        'slow': True,
    },

    'var_of_parameters_07': {
        'eq': f2 + 2*f(x).diff(x) + f(x) - x**2*exp(-x),
        'sol': [Eq(f(x), (C1 + x*(C2 + x**3/12))*exp(-x))],
        'slow': True,
    },

    'var_of_parameters_08': {
        'eq': f2 - 3*f(x).diff(x) + 2*f(x) - x*exp(-x),
        'sol': [Eq(f(x), C1*exp(x) + C2*exp(2*x) + (6*x + 5)*exp(-x)/36)],
        'slow': True,
    },

    'var_of_parameters_09': {
        'eq': f(x).diff(x, 3) - 3*f2 + 3*f(x).diff(x) - f(x) - exp(x),
        'sol': [Eq(f(x), (C1 + x*(C2 + x*(C3 + x/6)))*exp(x))],
        'slow': True,
    },

    'var_of_parameters_10': {
        'eq': f2 + 2*f(x).diff(x) + f(x) - exp(-x)/x,
        'sol': [Eq(f(x), (C1 + x*(C2 + log(x)))*exp(-x))],
        'slow': True,
    },

    'var_of_parameters_11': {
        'eq': f2 + f(x) - 1/sin(x)*1/cos(x),
        'sol': [Eq(f(x), (C1 + log(sin(x) - 1)/2 - log(sin(x) + 1)/2
        )*cos(x) + (C2 + log(cos(x) - 1)/2 - log(cos(x) + 1)/2)*sin(x))],
        'slow': True,
    },

    'var_of_parameters_12': {
        'eq': f(x).diff(x, 4) - 1/x,
        'sol': [Eq(f(x), C1 + C2*x + C3*x**2 + x**3*(C4 + log(x)/6))],
        'slow': True,
    },

    # These were from issue: https://github.com/sympy/sympy/issues/15996
    'var_of_parameters_13': {
        'eq': f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x) - 2*x - exp(I*x),
        'sol': [Eq(f(x), C1 + x**2 + (C2 + x*(C3 - x/8 + 3*exp(I*x)/2 + 3*exp(-I*x)/2) + 5*exp(2*I*x)/16 + 2*I*exp(I*x) - 2*I*exp(-I*x))*sin(x) + (C4 + x*(C5 + I*x/8 + 3*I*exp(I*x)/2 - 3*I*exp(-I*x)/2)
        + 5*I*exp(2*I*x)/16 - 2*exp(I*x) - 2*exp(-I*x))*cos(x) - I*exp(I*x))],
    },

    'var_of_parameters_14': {
        'eq': f(x).diff(x, 5) + 2*f(x).diff(x, 3) + f(x).diff(x) - exp(I*x),
        'sol': [Eq(f(x), C1 + (C2 + x*(C3 - x/8) + 5*exp(2*I*x)/16)*sin(x) + (C4 + x*(C5 + I*x/8) + 5*I*exp(2*I*x)/16)*cos(x) - I*exp(I*x))],
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_2nd_linear_bessel():
    return {
            'hint': "2nd_linear_bessel",
            'func': f(x),
            'examples':{
    '2nd_lin_bessel_01': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (x**2 - 4)*f(x),
        'sol': [Eq(f(x), C1*besselj(2, x) + C2*bessely(2, x))],
    },

    '2nd_lin_bessel_02': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (x**2 +25)*f(x),
        'sol': [Eq(f(x), C1*besselj(5*I, x) + C2*bessely(5*I, x))],
    },

    '2nd_lin_bessel_03': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (x**2)*f(x),
        'sol': [Eq(f(x), C1*besselj(0, x) + C2*bessely(0, x))],
    },

    '2nd_lin_bessel_04': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (81*x**2 -S(1)/9)*f(x),
        'sol': [Eq(f(x), C1*besselj(S(1)/3, 9*x) + C2*bessely(S(1)/3, 9*x))],
    },

    '2nd_lin_bessel_05': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (x**4 - 4)*f(x),
        'sol': [Eq(f(x), C1*besselj(1, x**2/2) + C2*bessely(1, x**2/2))],
    },

    '2nd_lin_bessel_06': {
        'eq': x**2*(f(x).diff(x, 2)) + 2*x*(f(x).diff(x)) + (x**4 - 4)*f(x),
        'sol': [Eq(f(x), (C1*besselj(sqrt(17)/4, x**2/2) + C2*bessely(sqrt(17)/4, x**2/2))/sqrt(x))],
    },

    '2nd_lin_bessel_07': {
        'eq': x**2*(f(x).diff(x, 2)) + x*(f(x).diff(x)) + (x**2 - S(1)/4)*f(x),
        'sol': [Eq(f(x), C1*besselj(S(1)/2, x) + C2*bessely(S(1)/2, x))],
    },

    '2nd_lin_bessel_08': {
        'eq': x**2*(f(x).diff(x, 2)) - 3*x*(f(x).diff(x)) + (4*x + 4)*f(x),
        'sol': [Eq(f(x), x**2*(C1*besselj(0, 4*sqrt(x)) + C2*bessely(0, 4*sqrt(x))))],
    },

    '2nd_lin_bessel_09': {
        'eq': x*(f(x).diff(x, 2)) - f(x).diff(x) + 4*x**3*f(x),
        'sol': [Eq(f(x), x*(C1*besselj(S(1)/2, x**2) + C2*bessely(S(1)/2, x**2)))],
    },

    '2nd_lin_bessel_10': {
        'eq': (x-2)**2*(f(x).diff(x, 2)) - (x-2)*f(x).diff(x) + 4*(x-2)**2*f(x),
        'sol': [Eq(f(x), (x - 2)*(C1*besselj(1, 2*x - 4) + C2*bessely(1, 2*x - 4)))],
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_2nd_2F1_hypergeometric():
    return {
            'hint': "2nd_hypergeometric",
            'func': f(x),
            'examples':{
    '2nd_2F1_hyper_01': {
        'eq': x*(x-1)*f(x).diff(x, 2) + (S(3)/2 -2*x)*f(x).diff(x) + 2*f(x),
        'sol': [Eq(f(x), C1*x**(S(5)/2)*hyper((S(3)/2, S(1)/2), (S(7)/2,), x) + C2*hyper((-1, -2), (-S(3)/2,), x))],
    },

    '2nd_2F1_hyper_02': {
        'eq': x*(x-1)*f(x).diff(x, 2) + (S(7)/2*x)*f(x).diff(x) + f(x),
        'sol': [Eq(f(x), (C1*(1 - x)**(S(5)/2)*hyper((S(1)/2, 2), (S(7)/2,), 1 - x) +
          C2*hyper((-S(1)/2, -2), (-S(3)/2,), 1 - x))/(x - 1)**(S(5)/2))],
    },

    '2nd_2F1_hyper_03': {
        'eq': x*(x-1)*f(x).diff(x, 2) + (S(3)+ S(7)/2*x)*f(x).diff(x) + f(x),
        'sol': [Eq(f(x), (C1*(1 - x)**(S(11)/2)*hyper((S(1)/2, 2), (S(13)/2,), 1 - x) +
          C2*hyper((-S(7)/2, -5), (-S(9)/2,), 1 - x))/(x - 1)**(S(11)/2))],
    },

    '2nd_2F1_hyper_04': {
        'eq': -x**(S(5)/7)*(-416*x**(S(9)/7)/9 - 2385*x**(S(5)/7)/49 + S(298)*x/3)*f(x)/(196*(-x**(S(6)/7) +
         x)**2*(x**(S(6)/7) + x)**2) + Derivative(f(x), (x, 2)),
        'sol': [Eq(f(x), x**(S(45)/98)*(C1*x**(S(4)/49)*hyper((S(1)/3, -S(1)/2), (S(9)/7,), x**(S(2)/7)) +
          C2*hyper((S(1)/21, -S(11)/14), (S(5)/7,), x**(S(2)/7)))/(x**(S(2)/7) - 1)**(S(19)/84))],
        'checkodesol_XFAIL':True,
    },
    }
    }


@_add_example_keys
def _get_examples_ode_sol_separable_reduced():
    df = f(x).diff(x)
    return {
            'hint': "separable_reduced",
            'func': f(x),
            'examples':{
    'separable_reduced_01': {
        'eq': x* df  + f(x)* (1 / (x**2*f(x) - 1)),
        'sol': [Eq(log(x**2*f(x))/3 + log(x**2*f(x) - Rational(3, 2))/6, C1 + log(x))],
        'simplify_flag': False,
        'XFAIL': ['lie_group'], #It hangs.
    },

    #Note: 'separable_reduced_02' is referred in 'separable_reduced_11'
    'separable_reduced_02': {
        'eq': f(x).diff(x) + (f(x) / (x**4*f(x) - x)),
        'sol': [Eq(log(x**3*f(x))/4 + log(x**3*f(x) - Rational(4,3))/12, C1 + log(x))],
        'simplify_flag': False,
        'checkodesol_XFAIL':True, #It hangs for this.
    },

    'separable_reduced_03': {
        'eq': x*df + f(x)*(x**2*f(x)),
        'sol': [Eq(log(x**2*f(x))/2 - log(x**2*f(x) - 2)/2, C1 + log(x))],
        'simplify_flag': False,
    },

    'separable_reduced_04': {
        'eq': Eq(f(x).diff(x) + f(x)/x * (1 + (x**(S(2)/3)*f(x))**2), 0),
        'sol': [Eq(-3*log(x**(S(2)/3)*f(x)) + 3*log(3*x**(S(4)/3)*f(x)**2 + 1)/2, C1 + log(x))],
        'simplify_flag': False,
    },

    'separable_reduced_05': {
        'eq': Eq(f(x).diff(x) + f(x)/x * (1 + (x*f(x))**2), 0),
        'sol': [Eq(f(x), -sqrt(2)*sqrt(1/(C1 + log(x)))/(2*x)),\
                   Eq(f(x), sqrt(2)*sqrt(1/(C1 + log(x)))/(2*x))],
    },

    'separable_reduced_06': {
        'eq': Eq(f(x).diff(x) + (x**4*f(x)**2 + x**2*f(x))*f(x)/(x*(x**6*f(x)**3 + x**4*f(x)**2)), 0),
        'sol': [Eq(f(x), C1 + 1/(2*x**2))],
    },

    'separable_reduced_07': {
        'eq': Eq(f(x).diff(x) + (f(x)**2)*f(x)/(x), 0),
        'sol': [Eq(f(x), -sqrt(2)*sqrt(1/(C1 + log(x)))/2),\
                  Eq(f(x), sqrt(2)*sqrt(1/(C1 + log(x)))/2)],
    },

    'separable_reduced_08': {
        'eq': Eq(f(x).diff(x) + (f(x)+3)*f(x)/(x*(f(x)+2)), 0),
        'sol': [Eq(-log(f(x) + 3)/3 - 2*log(f(x))/3, C1 + log(x))],
        'simplify_flag': False,
        'XFAIL': ['lie_group'], #It hangs.
    },

    'separable_reduced_09': {
        'eq': Eq(f(x).diff(x) + (f(x)+3)*f(x)/x, 0),
        'sol': [Eq(f(x), 3/(C1*x**3 - 1))],
    },

    'separable_reduced_10': {
        'eq': Eq(f(x).diff(x) + (f(x)**2+f(x))*f(x)/(x), 0),
        'sol': [Eq(- log(x) - log(f(x) + 1) + log(f(x)) + 1/f(x), C1)],
        'XFAIL': ['lie_group'],#No algorithms are implemented to solve equation -C1 + x*(_y + 1)*exp(-1/_y)/_y

    },

    # Equivalent to example_name 'separable_reduced_02'. Only difference is testing with simplify=True
    'separable_reduced_11': {
        'eq': f(x).diff(x) + (f(x) / (x**4*f(x) - x)),
        'sol': [Eq(f(x), -sqrt(2)*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)/6
- sqrt(2)*sqrt(-3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
+ 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 4/x**6
- 4*sqrt(2)/(x**9*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)))/6 + 1/(3*x**3)),
Eq(f(x), -sqrt(2)*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)/6
+ sqrt(2)*sqrt(-3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
+ 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 4/x**6
- 4*sqrt(2)/(x**9*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)))/6 + 1/(3*x**3)),
Eq(f(x), sqrt(2)*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)/6
- sqrt(2)*sqrt(-3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
+ 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
+ 4/x**6 + 4*sqrt(2)/(x**9*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)))/6 + 1/(3*x**3)),
Eq(f(x), sqrt(2)*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3)
- 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)/6
+ sqrt(2)*sqrt(-3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1)
+ x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 4/x**6 + 4*sqrt(2)/(x**9*sqrt(3*3**Rational(1,3)*(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1))
- exp(12*C1)/x**6)**Rational(1,3) - 3*3**Rational(2,3)*exp(12*C1)/(sqrt((3*exp(12*C1) + x**(-12))*exp(24*C1)) - exp(12*C1)/x**6)**Rational(1,3) + 2/x**6)))/6 + 1/(3*x**3))],
        'checkodesol_XFAIL':True, #It hangs for this.
        'slow': True,
    },

    #These were from issue: https://github.com/sympy/sympy/issues/6247
    'separable_reduced_12': {
        'eq': x**2*f(x)**2 + x*Derivative(f(x), x),
        'sol': [Eq(f(x), 2*C1/(C1*x**2 - 1))],
    },
    }
    }


def _get_all_examples():
    all_examples = _get_examples_ode_sol_euler_homogeneous + \
    _get_examples_ode_sol_euler_undetermined_coeff + \
    _get_examples_ode_sol_euler_var_para + \
    _get_examples_ode_sol_factorable + \
    _get_examples_ode_sol_bernoulli + \
    _get_examples_ode_sol_nth_algebraic + \
    _get_examples_ode_sol_riccati + \
    _get_examples_ode_sol_1st_linear + \
    _get_examples_ode_sol_1st_exact + \
    _get_examples_ode_sol_almost_linear + \
    _get_examples_ode_sol_nth_order_reducible + \
    _get_examples_ode_sol_nth_linear_undetermined_coefficients + \
    _get_examples_ode_sol_liouville + \
    _get_examples_ode_sol_separable + \
    _get_examples_ode_sol_nth_linear_var_of_parameters + \
    _get_examples_ode_sol_2nd_linear_bessel + \
    _get_examples_ode_sol_2nd_2F1_hypergeometric + \
    _get_examples_ode_sol_separable_reduced

    return all_examples
