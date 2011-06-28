import configobj
import _winreg
import os.path
import base64
import win32crypt, pywintypes

class WpkgConfigError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
    
class WpkgConfig(object):
    regkey = "Software\Policies\WPKG_GP"
    def __init__(self):
        with _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, R"SOFTWARE\Wpkg-GP", 0, _winreg.KEY_READ) as key:
            self.install_path = _winreg.QueryValueEx(key, "InstallPath")[0]
        self.inifile = os.path.join(self.install_path, "Wpkg-GP.ini")
        self.configobj = configobj.ConfigObj(self.inifile)
        self.WpkgConfig = self.configobj["WpkgConfig"]
        try:
            self.ignore_policy = int(self.WpkgConfig["IgnoreGroupPolicy"])
        except KeyError:
            self.ignore_policy = 0
        
        self.settings = [
            WpkgSetting(self, "WpkgCommand", None, "string", True),
            WpkgSetting(self, "WpkgVerbosity", 1, "int"),
            WpkgSetting(self, "WpkgMaxReboots", 10, "int"),
            WpkgSetting(self, "WpkgRebootPolicy", "force"),
            WpkgSetting(self, "WpkgTimeout", 15, "int"),
            WpkgSetting(self, "InstallOnShutdown", 1, "int"),
            WpkgSetting(self, "EnableViaLGP", 0, "int"),
            WpkgSetting(self, "WpkgNetworkUsername"),
            WpkgPasswordSetting(self, "WpkgNetworkPassword", None, "password"),
            WpkgSetting(self, "WpkgExecuteByNonAdmins", 0, "int"),
            WpkgSetting(self, "WpkgExecuteByLocalUsers", 1, "int")
            ]
    def get(self, name):
        for i in self.settings:
            if i.name == name:
                return i.get()
    def set(self, name, new_value):
        for i in self.settings:
            if i.name == name:
                i.set(new_value)

class WpkgSetting(object):
    def __init__(self, caller, name, default_value = None, type = "string", required = False):
        self.caller = caller
        self.name = name
        self.default_value = default_value
        self.type = type
        self.required = required
        
    def get_from_ini(self):
        try:
            ini_config =  self.caller.WpkgConfig[self.name]
        except KeyError:
            return None
        if ini_config == "":
            return None
        else:
            if self.type == "int":
                return int(ini_config)
            else:
                return ini_config
    
    def get_from_policy(self):
        try:
            with _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, self.caller.regkey) as key:
                if self.type == "int":
                    return int(_winreg.QueryValueEx(key, self.name)[0])
                else:
                    return _winreg.QueryValueEx(key, self.name)[0]
        except WindowsError:
            return None

    def get(self):
        if self.caller.ignore_policy != 1:
            policy_value = self.get_from_policy()
            if policy_value != None:
                return policy_value
        ini_value = self.get_from_ini()
        if ini_value != None:
            return ini_value
        if self.required == True and self.default_value == None:
            raise WpkgConfigError("The setting %s is required, but no value set by policy or in ini file" % self.name)
        else:
            return self.default_value
    
    def set(self, new_value):
        value = new_value
        self.caller.WpkgConfig[self.name] = value
        self.caller.confobj.write()

class WpkgPasswordSetting(WpkgSetting):
    def get(self):
        if self.caller.ignore_policy != "1":
            policy_value = self.get_from_policy()
            if policy_value != None:
                return policy_value
        ini_value = self.get_from_ini()
        if ini_value != None:
            self.passwordtype = ini_value.split(":")[0]
            value = ":".join(ini_value.split(":")[1:])
            if self.passwordtype == "clear":
                # Encrypt the password
                self.set(value)
                return value
            elif self.passwordtype == "crypt":
                #Remove base_64
                encrypted_password = base64.b64decode(value)
                password = win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1]
                return password
            else:
                raise WpkgConfigError("The password type %s is invalid, provide either 'clear:password' or 'crypt:encryptedpassword'" % self.passwordtype)
        else:
            return None
    def set(self, new_value):
        encrypted_password = win32crypt.CryptProtectData(new_value, "Password", None, None, None, 0)
        base64_password = base64.b64encode(encrypted_password)
        value = "crypt:%s" % base64_password
        self.caller.WpkgConfig[self.name] = value
        self.caller.configobj.write()

def main():
    config = WpkgConfig()
    for setting in config.settings:
        print "%s is %s" % (setting.name, setting.get())

if __name__ == '__main__':
    main()