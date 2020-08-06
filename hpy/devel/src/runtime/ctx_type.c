#include <stddef.h>
#include <Python.h>
#include "hpy.h"
#include "common/runtime/ctx_type.h"

#ifdef HPY_UNIVERSAL_ABI
   // for _h2py and _py2h
#  include "handles.h"
#endif


_HPy_HIDDEN void*
ctx_Cast(HPyContext ctx, HPy h)
{
    return _h2py(h);
}

static int
sig2flags(HPyFunc_Signature sig)
{
    switch(sig) {
        case HPyFunc_VARARGS:  return METH_VARARGS;
        case HPyFunc_KEYWORDS: return METH_VARARGS | METH_KEYWORDS;
        case HPyFunc_NOARGS:   return METH_NOARGS;
        case HPyFunc_O:        return METH_O;
        default:               return -1;
    }
}

static int
HPyDef_count(HPyDef *defs[], HPy_ssize_t *slot_count, HPy_ssize_t *meth_count)
{
    *slot_count = 0;
    *meth_count = 0;
    if (defs == NULL)
        return 0;
    for(int i=0; defs[i] != NULL; i++)
        switch(defs[i]->kind) {
        case HPyDef_Kind_Slot:
            (*slot_count)++;
            break;
        case HPyDef_Kind_Meth:
            (*meth_count)++;
            break;
        default:
            PyErr_Format(PyExc_ValueError, "Invalid HPyDef.kind: %ld", defs[i]->kind);
            return -1;
        }
    return 0;
}

static void
legacy_slots_count(PyType_Slot slots[], HPy_ssize_t *slot_count,
                   PyMethodDef **method_defs)
{
    *slot_count = 0;
    *method_defs = NULL;
    if (slots == NULL)
        return;
    for(int i=0; slots[i].slot != 0; i++)
        switch(slots[i].slot) {
        case Py_tp_methods:
            *method_defs = (PyMethodDef *)slots[i].pfunc;
            break;
        default:
            (*slot_count)++;
            break;
        }
}


/*
 * Create a PyMethodDef which contains:
 *     1. All HPyMeth contained in hpyspec->defines
 *     2. All the PyMethodDef contained inside legacy_methods
 *
 * Notes:
 *     - This function is also called from ctx_module.c.
 *     - This malloc()s a result which will never be freed. Too bad
 */
_HPy_HIDDEN PyMethodDef *
create_method_defs(HPyDef *hpydefs[], PyMethodDef *legacy_methods)
{
    // count the HPyMeth
    HPy_ssize_t hpyslot_count = 0;
    HPy_ssize_t hpymeth_count = 0;
    if (HPyDef_count(hpydefs, &hpyslot_count, &hpymeth_count) == -1)
        return NULL;
    // count the legacy methods
    HPy_ssize_t legacy_count = 0;
    if (legacy_methods != NULL) {
        while (legacy_methods[legacy_count].ml_name != NULL)
            legacy_count++;
    }
    HPy_ssize_t total_count = hpymeth_count + legacy_count;

    // allocate&fill the result
    PyMethodDef *result = PyMem_Malloc(sizeof(PyMethodDef) * (total_count+1));
    if (result == NULL) {
        PyErr_NoMemory();
        return NULL;
    }
    // copy the HPy methods
    int dst_idx = 0;
    if (hpydefs != NULL) {
        for(int i=0; hpydefs[i] != NULL; i++) {
            HPyDef *src = hpydefs[i];
            if (src->kind != HPyDef_Kind_Meth)
                continue;
            PyMethodDef *dst = &result[dst_idx++];
            dst->ml_name = src->meth.name;
            dst->ml_meth = src->meth.cpy_trampoline;
            dst->ml_flags = sig2flags(src->meth.signature);
            if (dst->ml_flags == -1) {
                PyMem_Free(result);
                PyErr_SetString(PyExc_ValueError,
                                "Unsupported HPyMeth signature");
                return NULL;
            }
            dst->ml_doc = src->meth.doc;
        }
    }
    // copy the legacy methods
    for(int i=0; i<legacy_count; i++) {
        PyMethodDef *src = &legacy_methods[i];
        PyMethodDef *dst = &result[dst_idx++];
        dst->ml_name = src->ml_name;
        dst->ml_meth = src->ml_meth;
        dst->ml_flags = src->ml_flags;
        dst->ml_doc = src->ml_doc;
    }
    result[dst_idx++] = (PyMethodDef){NULL, NULL, 0, NULL};
    return result;
}

static PyType_Slot *
create_slot_defs(HPyType_Spec *hpyspec)
{
    // count the HPySlots
    HPy_ssize_t hpyslot_count = 0;
    HPy_ssize_t hpymeth_count = 0;
    if (HPyDef_count(hpyspec->defines, &hpyslot_count, &hpymeth_count) == -1)
        return NULL;

    // add the legacy slots
    HPy_ssize_t legacy_slot_count = 0;
    PyMethodDef *legacy_method_defs = NULL;
    legacy_slots_count(hpyspec->legacy_slots, &legacy_slot_count,
                       &legacy_method_defs);

    // add a slot to hold Py_tp_methods
    hpyslot_count++;

    // allocate the result PyType_Slot array
    HPy_ssize_t total_slot_count = hpyslot_count + legacy_slot_count;
    PyType_Slot *result = PyMem_Malloc(
        sizeof(PyType_Slot) * (total_slot_count + 1));
    if (result == NULL)
        return NULL;

    // fill the result with non-meth slots
    int dst_idx = 0;
    if (hpyspec->defines != NULL) {
        for (int i = 0; hpyspec->defines[i] != NULL; i++) {
            HPyDef *src = hpyspec->defines[i];
            if (src->kind != HPyDef_Kind_Slot)
                continue;
            PyType_Slot *dst = &result[dst_idx++];
            dst->slot = src->slot.slot;
            dst->pfunc = src->slot.cpy_trampoline;
        }
    }

    // add the legacy slots (non-methods)
    if (hpyspec->legacy_slots != NULL) {
        PyType_Slot *legacy_slots = (PyType_Slot *)hpyspec->legacy_slots;
        for (int i = 0; legacy_slots[i].slot != 0; i++) {
            PyType_Slot *src = &legacy_slots[i];
            if (src->slot == Py_tp_methods)
                continue;
            PyType_Slot *dst = &result[dst_idx++];
            *dst = *src;
        }
    }

    // add the "real" methods
    PyMethodDef *m = create_method_defs(hpyspec->defines, legacy_method_defs);
    if (m == NULL) {
        PyMem_Free(result);
        return NULL;
    }
    result[dst_idx++] = (PyType_Slot){Py_tp_methods, m};

    // add the NULL sentinel at the end
    result[dst_idx++] = (PyType_Slot){0, NULL};
    return result;
}


_HPy_HIDDEN HPy
ctx_Type_FromSpec(HPyContext ctx, HPyType_Spec *hpyspec)
{
    PyType_Spec *spec = PyMem_Malloc(sizeof(PyType_Spec));
    if (spec == NULL) {
        PyErr_NoMemory();
        return HPy_NULL;
    }
    spec->name = hpyspec->name;
    spec->basicsize = hpyspec->basicsize;
    spec->itemsize = hpyspec->itemsize;
    spec->flags = hpyspec->flags;
    spec->slots = create_slot_defs(hpyspec);
    if (spec->slots == NULL) {
        PyMem_Free(spec);
        PyErr_NoMemory();
        return HPy_NULL;
    }
    PyObject *result = PyType_FromSpec(spec);
    /* note that we do NOT free the memory which was allocated by
       create_method_defs, because that one is referenced internally by
       CPython (which probably assumes it's statically allocated) */
    PyMem_Free(spec->slots);
    PyMem_Free(spec);
    return _py2h(result);
}

_HPy_HIDDEN HPy
ctx_New(HPyContext ctx, HPy h_type, void **data)
{
    PyObject *tp = _h2py(h_type);
    if (!PyType_Check(tp)) {
        PyErr_SetString(PyExc_TypeError, "HPy_New arg 1 must be a type");
        return HPy_NULL;
    }

    PyObject *result = PyObject_New(PyObject, (PyTypeObject*)tp);
    if (!result)
        return HPy_NULL;

    *data = (void*)result;
    return _py2h(result);
}

_HPy_HIDDEN HPy
ctx_Type_GenericNew(HPyContext ctx, HPy h_type, HPy *args, HPy_ssize_t nargs, HPy kw)
{
    PyTypeObject *type = (PyTypeObject *)_h2py(h_type);
    PyObject *res = type->tp_alloc(type, 0);
    return _py2h(res);
}
