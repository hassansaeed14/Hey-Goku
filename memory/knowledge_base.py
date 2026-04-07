from memory.memory_manager import remember, recall

def store_user_name(name):
    remember("user_name", name)

def get_user_name():
    return recall("user_name")

def store_info(key, value):
    remember(key, value)

def get_info(key):
    return recall(key)