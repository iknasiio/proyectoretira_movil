from pythonforandroid.recipe import PyProjectRecipe


class MaterialyoucolorRecipe(PyProjectRecipe):
    stl_lib_name = "c++_shared"
    version = "3.0.4"
    url = (
        "https://files.pythonhosted.org/packages/eb/23/"
        "2e63e7bdfcc1aa7ba955386ad09e3bd8a535a1092d7af501659b63cb6282/"
        "materialyoucolor-3.0.4.tar.gz"
    )

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["LDCXXSHARED"] = env["CXX"] + " -shared"
        return env


recipe = MaterialyoucolorRecipe()
