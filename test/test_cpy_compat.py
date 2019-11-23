from .support import HPyTest


class TestCPythonCompatibility(HPyTest):

    def test_frompyobject(self):
        mod = self.make_module("""
            #include <Python.h>
            HPy_METH_NOARGS(f)
            static HPy f_impl(HPyContext ctx, HPy self)
            {
                PyObject *o = PyList_New(0);

                Py_ssize_t initial_refcount = o->ob_refcnt;
                HPy h = HPy_FromPyObject(ctx, o);
                Py_ssize_t final_refcount = o->ob_refcnt;

                PyList_Append(o, PyLong_FromSsize_t(final_refcount -
                                                    initial_refcount));
                Py_DECREF(o);
                return h;
            }
            @EXPORT f METH_NOARGS
            @INIT
        """)
        x = mod.f()
        assert x == [+1]

    def test_hpy_close(self):
        mod = self.make_module("""
            #include <Python.h>
            HPy_METH_NOARGS(f)
            static HPy f_impl(HPyContext ctx, HPy self)
            {
                PyObject *o = PyList_New(0);

                HPy h = HPy_FromPyObject(ctx, o);
                Py_ssize_t initial_refcount = o->ob_refcnt;
                HPy_Close(ctx, h);
                Py_ssize_t final_refcount = o->ob_refcnt;

                Py_DECREF(o);
                return HPyLong_FromLong(ctx, (long)(final_refcount -
                                                    initial_refcount));
            }
            @EXPORT f METH_NOARGS
            @INIT
        """)
        assert mod.f() == -1

    def test_hpy_dup(self):
        mod = self.make_module("""
            #include <Python.h>
            HPy_METH_NOARGS(f)
            static HPy f_impl(HPyContext ctx, HPy self)
            {
                PyObject *o = PyList_New(0);

                HPy h = HPy_FromPyObject(ctx, o);
                Py_ssize_t initial_refcount = o->ob_refcnt;
                HPy h2 = HPy_Dup(ctx, h);
                Py_ssize_t final_refcount = o->ob_refcnt;

                HPy_Close(ctx, h);
                HPy_Close(ctx, h2);
                Py_DECREF(o);
                return HPyLong_FromLong(ctx, (long)(final_refcount -
                                                    initial_refcount));
            }
            @EXPORT f METH_NOARGS
            @INIT
        """)
        assert mod.f() == +1

    def test_many_handles(self):
        mod = self.make_module("""
            #include <Python.h>
            #define NUM_HANDLES  10000

            HPy_METH_NOARGS(f)
            static HPy f_impl(HPyContext ctx, HPy self)
            {
                PyObject *o = PyList_New(0);

                Py_ssize_t result = -42;
                HPy handles[NUM_HANDLES];
                int i;
                Py_ssize_t initial_refcount = o->ob_refcnt;
                for (i = 0; i < NUM_HANDLES; i++)
                    handles[i] = HPy_FromPyObject(ctx, o);
                for (i = 0; i < NUM_HANDLES; i++)
                    if (HPy_IsNull(handles[i]))
                        goto error;
                for (i = 0; i < NUM_HANDLES; i++)
                    HPy_Close(ctx, handles[i]);
                Py_ssize_t final_refcount = o->ob_refcnt;
                result = final_refcount - initial_refcount;

             error:
                return HPyLong_FromLong(ctx, (long)result);
            }
            @EXPORT f METH_NOARGS
            @INIT
        """)
        assert mod.f() == 0

    def test_meth_cpy_noargs(self):
        mod = self.make_module("""
            #include <Python.h>

            HPy_METH_CPY_NOARGS(f)
            static PyObject *f_impl(PyObject *self, PyObject *args)
            {
                return PyLong_FromLong(1234);
            }
            @EXPORT f METH_CPY_NOARGS
            @INIT
        """)
        assert mod.f() == 1234

    def test_meth_cpy_o(self):
        mod = self.make_module("""
            #include <Python.h>

            HPy_METH_CPY_O(f)
            static PyObject *f_impl(PyObject *self, PyObject *arg)
            {
                long x = PyLong_AsLong(arg);
                return PyLong_FromLong(x * 2);
            }
            @EXPORT f METH_CPY_O
            @INIT
        """)
        assert mod.f(45) == 90

    def test_meth_cpy_varargs(self):
        mod = self.make_module("""
            #include <Python.h>

            HPy_METH_CPY_VARARGS(f)
            static PyObject *f_impl(PyObject *self, PyObject *args)
            {
                long a, b, c;
                if (!PyArg_ParseTuple(args, "lll", &a, &b, &c))
                    return NULL;
                return PyLong_FromLong(100*a + 10*b + c);
            }
            @EXPORT f METH_CPY_VARARGS
            @INIT
        """)
        assert mod.f(4, 5, 6) == 456
