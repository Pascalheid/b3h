# -*- coding: utf-8 -*-
"""
Created on Sun Feb 16 18:03:05 2020

@author: Wilms
"""
from scipy.optimize.optimize import wrap_function

def fmin_bfgs(fun, x0, fprime = None, data, args = (), gtol = 1e-5, norm = Inf,
              epsilon = _epsilon, maxiter = None, full_output = 0, disp = 1,
              retall = 0, callback = None):
    """
    Minimize a function using the BHHH algorithm.

    Parameters
    ----------
    fun : callable f(x,*args)
        Objective function to be minimized.
    x0 : ndarray
        Initial guess.
    fprime : callable f'(x,*args), optional
        Gradient of f.
    data : ndarray
        Data points on which to fit the likelihood function to.
    args : tuple, optional
        Extra arguments passed to f and fprime.
    gtol : float, optional
        Gradient norm must be less than gtol before successful termination.
    norm : float, optional
        Order of norm (Inf is max, -Inf is min)
    epsilon : int or ndarray, optional
        If fprime is approximated, use this value for the step size.
    callback : callable, optional
        An optional user-supplied function to call after each
        iteration.  Called as callback(xk), where xk is the
        current parameter vector.
    maxiter : int, optional
        Maximum number of iterations to perform.
    full_output : bool, optional
        If True,return fopt, func_calls, grad_calls, and warnflag
        in addition to xopt.
    disp : bool, optional
        Print convergence message if True.
    retall : bool, optional
        Return a list of results at each iteration if True.

    Returns
    -------
    xopt : ndarray
        Parameters which minimize f, i.e. f(xopt) == fopt.
    fopt : float
        Minimum value.
    gopt : ndarray
        Value of gradient at minimum, f'(xopt), which should be near 0.
    Bopt : ndarray
        Value of 1/f''(xopt), i.e. the inverse hessian matrix.
    func_calls : int
        Number of function_calls made.
    grad_calls : int
        Number of gradient calls made.
    warnflag : integer
        1 : Maximum number of iterations exceeded.
        2 : Gradient and/or function calls not changing.
        3 : NaN result encountered.
    allvecs  :  list
        The value of xopt at each iteration.  Only returned if retall is True.

    See also
    --------
    minimize: Interface to minimization algorithms for multivariate
        functions. See the 'BFGS' `method` in particular.

    Notes
    -----
    Optimize the function, f, whose gradient is given by fprime
    using the quasi-Newton method of Broyden, Fletcher, Goldfarb,
    and Shanno (BFGS)

    References
    ----------
    Wright, and Nocedal 'Numerical Optimization', 1999, pg. 198.

    """
    opts = {'gtol': gtol,
            'norm': norm,
            'eps': epsilon, # Noch einzubauen
            'disp': disp,
            'maxiter': maxiter,
            'return_all': retall}

    res = _minimize_bhhh(f, x0, data, args, fprime, callback = callback, **opts)

    if full_output:
        retlist = (res['x'], res['fun'], res['jac'], res['hess_inv'],
                   res['nfev'], res['njev'], res['status'])
        if retall:
            retlist += (res['allvecs'], )
        return retlist
    else:
        if retall:
            return res['x'], res['allvecs']
        else:
            return res['x']


def _minimize_bhhh(fun, x0, data, args = (), jac = None, callback = None,
                   gtol = 1e-5, norm = Inf, eps = _epsilon, maxiter = None,
                   disp = False, return_all = False,
                   **unknown_options):
    """
    Minimization of scalar function of one or more variables using the
    BFGS algorithm.

    Options
    -------
    disp : bool
        Set to True to print convergence messages.
    maxiter : int
        Maximum number of iterations to perform.
    gtol : float
        Gradient norm must be less than `gtol` before successful
        termination.
    norm : float
        Order of norm (Inf is max, -Inf is min).
    eps : float or ndarray
        If `jac` is approximated, use this value for the step size.

    """
    _check_unknown_options(unknown_options)
    
    f = fun
    fprime = jac
    epsilon = eps
    retall = return_all
    k = 0
    N = len(x0)
    nobs = data.shape[0]
    
    x0 = asarray(x0).flatten()
    if x0.ndim == 0:
        x0.shape = (1,)
    if maxiter is None:
        maxiter = len(x0) * 200
    func_calls, f = wrap_function(f, args)

    old_fval = f_agg(x0)
    
    # Change way the gradient is calculated.
    # Adapt this part to grad function. Need aggregate and individual gradient
    if callable(fprime):
        grad_calls, myfprime = wrap_function(fprime, args)
    else:
        grad_calls, myfprime = wrap_function(grad, args)
    
    # Need aggregate gradient at this point
    gfk = myfprime(x0)
    
    # Sets the initial step guess to dx ~ 1
    old_old_fval = old_fval + np.linalg.norm(gfk) / 2

    xk = x0
    if retall:
        allvecs = [x0]
    warnflag = 0
    gnorm = vecnorm(gfk, ord = norm)
    while (gnorm > gtol) and (k < maxiter): # for loop instead.
        
        # Individual
        gfk_obs = myfprime(xk)
        
        # Aggregate
        gfk = myfprime_agg(xk)

        # Check tolerance of gradient norm
        gnorm = vecnorm(gfk, ord = norm)
        if (gnorm <= gtol):
            break
        
        # Calculate BHHH hessian and step
        Hk = approx_hess_bhhh(gfk_obs)
        Bk = np.linalg.inv(Hk)
        pk = - numpy.dot(Bk, gfk)
        try:
            alpha_k, fc, gc, old_fval, old_old_fval, gfkp1 = \
                     _line_search_wolfe12(f_agg, myfprime_agg, xk, pk, gfk,
                                          old_fval, old_old_fval, 
                                          amin=1e-100, amax=1e100)
        except _LineSearchError:
            # Line search failed to find a better solution.
            warnflag = 2
            break

        xkp1 = xk + alpha_k * pk
        if retall:
            allvecs.append(xkp1)
        xk = xkp1
        if callback is not None:
            callback(xk)
        k += 1

        if not numpy.isfinite(old_fval):
            # We correctly found +-Inf as optimal value, or something went
            # wrong.
            warnflag = 2
            break

    fval = old_fval

    if warnflag == 2:
        msg = _status_message['pr_loss']
    elif k >= maxiter:
        warnflag = 1
        msg = _status_message['maxiter']
    elif np.isnan(gnorm) or np.isnan(fval) or np.isnan(xk).any():
        warnflag = 3
        msg = _status_message['nan']
    else:
        msg = _status_message['success']

    if disp:
        print("%s%s" % ("Warning: " if warnflag != 0 else "", msg))
        print("         Current function value: %f" % fval)
        print("         Iterations: %d" % k)
        print("         Function evaluations: %d" % func_calls[0])
        print("         Gradient evaluations: %d" % grad_calls[0])

    result = OptimizeResult(fun = fval, jac = gfk, hess_inv = Hk, 
                            nfev = func_calls[0],
                            njev = grad_calls[0], 
                            status = warnflag,
                            success = (warnflag == 0), 
                            message = msg, x = xk, nit = k)
    if retall:
        result['allvecs'] = allvecs
    return result