"""
NOTE: these tests are also meant to be run as PyPy "applevel" tests.

This means that global imports will NOT be visible inside the test
functions. In particular, you have to "import pytest" inside the test in order
to be able to use e.g. pytest.raises (which on PyPy will be implemented by a
"fake pytest module")
"""
from .support import HPyTest, DefaultExtensionTemplate


class PointTemplate(DefaultExtensionTemplate):
    """
    ExtensionTemplate with extra markers which helps to define again and again
    a simple Point type. Note that every test can use a different combination
    of markers, to test different features.
    """

    def DEFINE_PointObject(self):
        return """
            typedef struct {
                HPyObject_HEAD
                long x;
                long y;
            } PointObject;
        """

    def DEFINE_Point_new(self):
        return """
            HPyDef_SLOT(Point_new, HPy_tp_new, Point_new_impl, HPyFunc_KEYWORDS)
            static HPy Point_new_impl(HPyContext ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                long x, y;
                if (!HPyArg_Parse(ctx, args, nargs, "ll", &x, &y))
                    return HPy_NULL;
                PointObject *point;
                HPy h_point = HPy_New(ctx, cls, &point);
                if (HPy_IsNull(h_point))
                    return HPy_NULL;
                point->x = x;
                point->y = y;
                return h_point;
            }
        """

    def DEFINE_Point_xy(self):
        return """
            HPyDef_MEMBER(Point_x, "x", HPyMember_LONG, offsetof(PointObject, x))
            HPyDef_MEMBER(Point_y, "y", HPyMember_LONG, offsetof(PointObject, y))
        """

    def EXPORT_POINT_TYPE(self, *defines):
        defines += ('NULL',)
        defines = ', '.join(defines)
        #
        self.EXPORT_TYPE('"Point"', "Point_spec")
        return """
            static HPyDef *Point_defines[] = { %s };
            static HPyType_Spec Point_spec = {
                .name = "mytest.Point",
                .basicsize = sizeof(PointObject),
                .defines = Point_defines
            };
        """ % defines



class TestType(HPyTest):

    ExtensionTemplate = PointTemplate

    def test_simple_type(self):
        mod = self.make_module("""
            static HPyType_Spec Dummy_spec = {
                .name = "mytest.Dummy",
                .itemsize = 0,
                .flags = HPy_TPFLAGS_DEFAULT | HPy_TPFLAGS_BASETYPE,
            };

            @EXPORT_TYPE("Dummy", Dummy_spec)
            @INIT
        """)
        assert isinstance(mod.Dummy, type)
        assert mod.Dummy.__name__ == 'Dummy'
        assert mod.Dummy.__module__ == 'mytest'
        assert isinstance(mod.Dummy(), mod.Dummy)

        class Sub(mod.Dummy):
            pass
        assert isinstance(Sub(), mod.Dummy)

    def test_HPyDef_SLOT(self):
        mod = self.make_module("""
            HPyDef_SLOT(Dummy_repr, HPy_tp_repr, Dummy_repr_impl, HPyFunc_REPRFUNC);
            static HPy Dummy_repr_impl(HPyContext ctx, HPy self)
            {
                return HPyUnicode_FromString(ctx, "<Dummy>");
            }

            HPyDef_SLOT(Dummy_abs, HPy_nb_absolute, Dummy_abs_impl, HPyFunc_UNARYFUNC);
            static HPy Dummy_abs_impl(HPyContext ctx, HPy self)
            {
                return HPyLong_FromLong(ctx, 1234);
            }

            static HPyDef *Dummy_defines[] = {
                &Dummy_repr,
                &Dummy_abs,
                NULL
            };
            static HPyType_Spec Dummy_spec = {
                .name = "mytest.Dummy",
                .defines = Dummy_defines
            };

            @EXPORT_TYPE("Dummy", Dummy_spec)
            @INIT
        """)
        d = mod.Dummy()
        assert repr(d) == '<Dummy>'
        assert abs(d) == 1234

    def test_HPyDef_METH(self):
        import pytest
        mod = self.make_module("""
            HPyDef_METH(Dummy_foo, "foo", Dummy_foo_impl, HPyFunc_O)
            static HPy Dummy_foo_impl(HPyContext ctx, HPy self, HPy arg)
            {
                return HPy_Add(ctx, arg, arg);
            }

            HPyDef_METH(Dummy_bar, "bar", Dummy_bar_impl, HPyFunc_NOARGS)
            static HPy Dummy_bar_impl(HPyContext ctx, HPy self)
            {
                return HPyLong_FromLong(ctx, 1234);
            }

            HPyDef_METH(Dummy_identity, "identity", Dummy_identity_impl, HPyFunc_NOARGS)
            static HPy Dummy_identity_impl(HPyContext ctx, HPy self)
            {
                return HPy_Dup(ctx, self);
            }

            static HPyDef *dummy_type_defines[] = {
                    &Dummy_foo,
                    &Dummy_bar,
                    &Dummy_identity,
                    NULL
            };

            static HPyType_Spec dummy_type_spec = {
                .name = "mytest.Dummy",
                .defines = dummy_type_defines
            };

            @EXPORT_TYPE("Dummy", dummy_type_spec)
            @INIT
        """)
        d = mod.Dummy()
        assert d.foo(21) == 42
        assert d.bar() == 1234
        assert d.identity() is d
        with pytest.raises(TypeError):
            mod.Dummy.identity()
        class A: pass
        with pytest.raises(TypeError):
            mod.Dummy.identity(A())

    def test_HPy_New(self):
        mod = self.make_module("""
            @DEFINE_PointObject
            @DEFINE_Point_new

            HPyDef_METH(Point_foo, "foo", Point_foo_impl, HPyFunc_NOARGS)
            static HPy Point_foo_impl(HPyContext ctx, HPy self)
            {
                PointObject *point = HPy_CAST(ctx, PointObject, self);
                return HPyLong_FromLong(ctx, point->x*10 + point->y);
            }

            @EXPORT_POINT_TYPE(&Point_new, &Point_foo)
            @INIT
        """)
        p1 = mod.Point(7, 3)
        assert p1.foo() == 73
        p2 = mod.Point(4, 2)
        assert p2.foo() == 42


    def test_HPyDef_Member(self):
        mod = self.make_module("""
            @DEFINE_PointObject
            @DEFINE_Point_new
            @DEFINE_Point_xy
            @EXPORT_POINT_TYPE(&Point_new, &Point_x, &Point_y)
            @INIT
        """)
        p = mod.Point(7, 3)
        assert p.x == 7
        assert p.y == 3
        p.x = 123
        p.y = 456
        assert p.x == 123
        assert p.y == 456


    def test_HPyType_GenericNew(self):
        mod = self.make_module("""
            @DEFINE_PointObject
            @DEFINE_Point_xy

            HPyDef_SLOT(Point_new, HPy_tp_new, HPyType_GenericNew, HPyFunc_KEYWORDS)

            @EXPORT_POINT_TYPE(&Point_new, &Point_x, &Point_y)
            @INIT
        """)
        p = mod.Point()
        assert p.x == 0
        assert p.y == 0

    def test_tp_init(self):
        mod = self.make_module("""
            @DEFINE_PointObject
            @DEFINE_Point_xy

            HPyDef_SLOT(Point_new, HPy_tp_new, HPyType_GenericNew, HPyFunc_KEYWORDS)

            HPyDef_SLOT(Point_init, HPy_tp_init, Point_init_impl, HPyFunc_INITPROC)
            static int Point_init_impl(HPyContext ctx, HPy self, HPy *args,
                                       HPy_ssize_t nargs, HPy kw)
            {
                long x, y;
                if (!HPyArg_Parse(ctx, args, nargs, "ll", &x, &y))
                    return -1;

                PointObject *p = HPy_CAST(ctx, PointObject, self);
                p->x = x;
                p->y = y;
                return 0;
            }

            @EXPORT_POINT_TYPE(&Point_new, &Point_init, &Point_x, &Point_y)
            @INIT
        """)
        p = mod.Point(1, 2)
        assert p.x == 1
        assert p.y == 2

    def test_sq_item(self):
        mod = self.make_module("""
            HPyDef_SLOT(Dummy_getitem, HPy_sq_item, Dummy_getitem_impl, HPyFunc_SSIZEARGFUNC);
            static HPy Dummy_getitem_impl(HPyContext ctx, HPy self, HPy_ssize_t idx)
            {
                return HPyLong_FromLong(ctx, (long)idx*2);
            }

            static HPyDef *Dummy_defines[] = {
                &Dummy_getitem,
                NULL
            };
            static HPyType_Spec Dummy_spec = {
                .name = "mytest.Dummy",
                .defines =  Dummy_defines
            };

            @EXPORT_TYPE("Dummy", Dummy_spec)
            @INIT
        """)
        d = mod.Dummy()
        assert d[4] == 8
        assert d[21] == 42

    def test_tp_destroy(self):
        import gc
        mod = self.make_module("""
            typedef struct {
                HPyObject_HEAD
                long x, y;
            } PointObject;

            static long destroyed_x;

            HPyDef_SLOT(Point_new, HPy_tp_new, Point_new_impl, HPyFunc_KEYWORDS)
            static HPy Point_new_impl(HPyContext ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                PointObject *point;
                HPy h_point = HPy_New(ctx, cls, &point);
                if (HPy_IsNull(h_point))
                    return HPy_NULL;
                point->x = 7;
                point->y = 3;
                return h_point;
            }

            HPyDef_SLOT(Point_destroy, HPy_tp_destroy, Point_destroy_impl, HPyFunc_DESTROYFUNC)
            static void Point_destroy_impl(void *obj)
            {
                PointObject *point = (PointObject *)obj;
                destroyed_x += point->x;
            }

            static HPyDef *Point_defines[] = {
                &Point_new,
                &Point_destroy,
                NULL
            };
            static HPyType_Spec Point_spec = {
                .name = "mytest.Point",
                .basicsize = sizeof(PointObject),
                .defines = Point_defines
            };

            HPyDef_METH(f, "f", f_impl, HPyFunc_NOARGS)
            static HPy f_impl(HPyContext ctx, HPy self)
            {
                return HPyLong_FromLong(ctx, destroyed_x);
            }

            @EXPORT_TYPE("Point", Point_spec)
            @EXPORT(f)
            @INIT
        """)
        point = mod.Point()
        assert mod.f() == 0
        del point
        gc.collect()
        assert mod.f() == 7
        gc.collect()
        assert mod.f() == 7


    def test_HPyDef_GET(self):
        mod = self.make_module("""
            typedef struct {
                HPyObject_HEAD
                long x;
                long y;
            } PointObject;

            HPyDef_SLOT(Point_new, HPy_tp_new, Point_new_impl, HPyFunc_KEYWORDS)
            static HPy Point_new_impl(HPyContext ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                PointObject *point;
                HPy h_point = HPy_New(ctx, cls, &point);
                if (HPy_IsNull(h_point))
                    return HPy_NULL;
                point->x = 7;
                point->y = 3;
                return h_point;
            }

            HPyDef_GET(Point_z, "z", Point_z_get)
            static HPy Point_z_get(HPyContext ctx, HPy self, void *closure)
            {
                PointObject *point = HPy_CAST(ctx, PointObject, self);
                return HPyLong_FromLong(ctx, point->x*10 + point->y);
            }

            static HPyDef *Point_defines[] = {
                &Point_new,
                &Point_z,
                NULL
            };
            static HPyType_Spec Point_spec = {
                .name = "mytest.Point",
                .basicsize = sizeof(PointObject),
                .defines = Point_defines
            };

            @EXPORT_TYPE("Point", Point_spec)
            @INIT
        """)
        p = mod.Point()
        assert p.z == 73

    def test_HPyDef_GETSET(self):
        mod = self.make_module("""
            typedef struct {
                HPyObject_HEAD
                long x;
                long y;
            } PointObject;

            HPyDef_SLOT(Point_new, HPy_tp_new, Point_new_impl, HPyFunc_KEYWORDS)
            static HPy Point_new_impl(HPyContext ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                PointObject *point;
                HPy h_point = HPy_New(ctx, cls, &point);
                if (HPy_IsNull(h_point))
                    return HPy_NULL;
                point->x = 7;
                point->y = 3;
                return h_point;
            }

            HPyDef_GETSET(Point_z, "z", Point_z_get, Point_z_set, .closure=(void *)1000)
            static HPy Point_z_get(HPyContext ctx, HPy self, void *closure)
            {
                PointObject *point = HPy_CAST(ctx, PointObject, self);
                return HPyLong_FromLong(ctx, point->x*10 + point->y + (long)closure);
            }
            static int Point_z_set(HPyContext ctx, HPy self, HPy value, void *closure)
            {
                PointObject *point = HPy_CAST(ctx, PointObject, self);
                long current = point->x*10 + point->y + (long)closure;
                long target = HPyLong_AsLong(ctx, value);  // assume no exception
                point->y += target - current;
                return 0;
            }

            static HPyDef *Point_defines[] = {
                &Point_new,
                &Point_z,
                NULL
            };
            static HPyType_Spec Point_spec = {
                .name = "mytest.Point",
                .basicsize = sizeof(PointObject),
                .defines = Point_defines
            };

            @EXPORT_TYPE("Point", Point_spec)
            @INIT
        """)
        p = mod.Point()
        assert p.z == 1073
        p.z = 1075
        assert p.z == 1075

    def test_HPyDef_SET(self):
        mod = self.make_module("""
            typedef struct {
                HPyObject_HEAD
                long x;
                long y;
            } PointObject;

            HPyDef_SLOT(Point_new, HPy_tp_new, Point_new_impl, HPyFunc_KEYWORDS)
            static HPy Point_new_impl(HPyContext ctx, HPy cls, HPy *args,
                                      HPy_ssize_t nargs, HPy kw)
            {
                PointObject *point;
                HPy h_point = HPy_New(ctx, cls, &point);
                if (HPy_IsNull(h_point))
                    return HPy_NULL;
                point->x = 7;
                point->y = 3;
                return h_point;
            }

            HPyDef_SET(Point_z, "z", Point_z_set, .closure=(void *)1000)
            static int Point_z_set(HPyContext ctx, HPy self, HPy value, void *closure)
            {
                PointObject *point = HPy_CAST(ctx, PointObject, self);
                long current = point->x*10 + point->y + (long)closure;
                long target = HPyLong_AsLong(ctx, value);  // assume no exception
                point->y += target - current;
                return 0;
            }

            HPyDef_MEMBER(Point_y, "y", HPyMember_LONG, offsetof(PointObject, y))

            static HPyDef *Point_defines[] = {
                &Point_new,
                &Point_z,
                &Point_y,
                NULL
            };
            static HPyType_Spec Point_spec = {
                .name = "mytest.Point",
                .basicsize = sizeof(PointObject),
                .defines = Point_defines
            };

            @EXPORT_TYPE("Point", Point_spec)
            @INIT
        """)
        p = mod.Point()
        assert p.y == 3
        p.z = 1075
        assert p.y == 5
