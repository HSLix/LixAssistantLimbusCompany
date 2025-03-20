# coding: utf-8
# 参考 https://blog.csdn.net/weixin_44966641/article/details/131077331
class CustomActionDict(dict):
    def __init__(self, *args, **kwargs):
        super(CustomActionDict, self).__init__(*args, **kwargs)
        self._dict = {}

    def __call__(self, target):
        return self.register(target)

    def register(self, target):
        def add_item(key, value):
            if not callable(value):
                raise Exception(f"Error:{value} must be callable!")
            if key in self._dict:
                print(f"\033[31mWarning:\033[0m {value.__name__} already exists and will be overwritten!")
            self[key] = value
            return value

        if callable(target):    # 传入的target可调用 --> 没有给注册名 --> 传入的函数名或类名作为注册名
            return add_item(target.__name__, target)
        else:                   # 不可调用 --> 传入了注册名 --> 作为可调用对象的注册名 
            return lambda x : add_item(target, x)


    


def init():
    @register_func.register
    def add(a, b):
        return a + b

    @register_func.register
    def multiply(a, b):
        return a * b

    @register_func.register('matrix multiply')
    def multiply(a, b):
        pass

    @register_func.register
    def minus(a, b):
        return a - b

if __name__ == "__main__":
    register_func = CustomActionDict()
    init()

    # @register_func.register
    # def minus(a, b):
    #     return a - b

    for k, v in register_func.items():
        print(f"key: {k}, value: {v}")
