#ifndef HPY_UNIVERSAL_HPYFUNC_H
#define HPY_UNIVERSAL_HPYFUNC_H

typedef enum {
    HPyFunc_VARARGS  = 1,  // METH_VARARGS
    HPyFunc_KEYWORDS = 2,  // METH_VARARGS | METH_KEYWORDS
    HPyFunc_NOARGS   = 3,  // METH_NOARGS
    HPyFunc_O        = 4   // METH_O
} HPyFunc_Signature;

// typedefs corresponding to the various HPyFunc_Signature members
typedef HPy (*HPyFunc_noargs)(HPyContext ctx, HPy self);
typedef HPy (*HPyFunc_o)(HPyContext ctx, HPy self, HPy arg);
typedef HPy (*HPyFunc_varargs)(HPyContext ctx, HPy self, HPy *args, HPy_ssize_t nargs);
typedef HPy (*HPyFunc_keywords)(HPyContext ctx, HPy self,
                                HPy *args, HPy_ssize_t nargs, HPy kw);


/* Emit a forward declaration for a function SYM having a signature SIG, where
   SIG is one of HPyFunc_Signature members.

   Strictly speaking, the anonymous enum is not needed, since it just defines
   a constant like Foo_sig which is never used anyway. However, since we try
   to use "SIG" in the enum definition, we get a very nice error message in
   case we use a SIG value which does not exists.  If we didn't use this
   trick, we would get a VERY obscure error message, since gcc would see a
   function call to something like _HPyFunc_DECLARE_HPyFunc_XXX.
*/
#define HPyFunc_DECLARE(SYM, SIG) \
    enum { SYM##_sig = SIG };     \
    _HPyFunc_DECLARE_##SIG(SYM)


/* Emit a CPython-compatible trampoline which calls IMPL, where IMPL has the
   signature SIG. See above for why we need the anonymous enum. The actual
   implementation of trampolines are in hpyfunc_trampolines.h, which is
   different for the CPython and Universal cases */
#define HPyFunc_TRAMPOLINE(SYM, IMPL, SIG) \
    enum { SYM##_sig = SIG };              \
    _HPyFunc_TRAMPOLINE_##SIG(SYM, IMPL)


#include "autogen_hpyfunc_declare.h"


#ifdef HPY_UNIVERSAL_ABI
#  include "universal/hpyfunc_trampolines.h"
#else
#  include "cpython/hpyfunc_trampolines.h"
#endif // HPY_UNIVERSAL_ABI

#endif /* HPY_UNIVERSAL_HPYFUNC_H */
