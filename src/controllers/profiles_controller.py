from PySide6.QtCore import QObject

class ProfilesController(QObject):
    def __init__(self, mods_model, profiles_view):
        super().__init__()

        self.mods_model = mods_model
        self.view = profiles_view
        
        self.view.onSwitchProfileRequested.connect(self.change_profile)
        self.view.onCreateProfileRequested.connect(self.create_profile)
        
        self.mods_model.onProfileChanged.connect(self.refresh_profiles)
        
        self.refresh_profiles()
    
    def refresh_profiles(self):
        """Refresh the list of profiles in the view."""
        self.view.update_profiles(self.mods_model.get_profiles())

    def change_profile(self, profile_id: str):
        self.mods_model.switch_profile(profile_id)
    
    def create_profile(self):
        result, profile_name, profile_desc = self.view.show_create_profile_modal()
        
        if result:
            profile_id = self.mods_model.create_profile(profile_name, profile_desc)
            self.mods_model.switch_profile(profile_id)  