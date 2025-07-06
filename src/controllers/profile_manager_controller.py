from PySide6.QtCore import QObject, Slot, Signal

from src.models.profile_manager_model import (
    ProfileAlreadyExistsError,
    ProfileManager,
    ProfileInUseError,
    ProfileNotFoundError,
)

class ProfileManagerController(QObject):
    notificationRequested = Signal(str, str, str, int)

    def __init__(self, profile_manager_model: ProfileManager, view) -> None:
        super().__init__()
        self.model = profile_manager_model
        self.view = view

        self.view.addProfile.connect(self._add_profile)
        self.view.editProfile.connect(self._edit_profile)
        self.view.deleteProfile.connect(self._delete_profile)

        self.model.profilesChanged.connect(self.refresh_profiles)
        
        self.refresh_profiles()

    def refresh_profiles(self) -> None:
        profiles = self.model.get_profiles()
        self.view.refresh_profiles_list(profiles)

    @Slot(str, str)
    def _add_profile(self, name: str, description: str) -> None:
        try:
            self.model.create_profile(name, description)
        except ProfileAlreadyExistsError:
            self.notificationRequested.emit(
                self.tr("Duplicate Profile"),
                self.tr(f"A profile named '{name}' already exists."),
                "warning",
                3000,
            )

    @Slot(str, str, str)
    def _edit_profile(self, profile_id: str, name: str, description: str) -> None:
        try:
            self.model.edit_profile(profile_id, name, description)
        except ProfileNotFoundError:
            self.notificationRequested.emit(
                self.tr("Error"),
                self.tr("Profile not found. It may have already been deleted."),
                "error",
                3000,
            )
        except ProfileAlreadyExistsError:
            self.notificationRequested.emit(
                self.tr("Duplicate Profile"),
                self.tr(f"A profile named '{name}' already exists."),
                "warning",
                3000,
            )

    @Slot(str)
    def _delete_profile(self, profile_id: str) -> None:
        try:
            self.model.delete_profile(profile_id)
        except ProfileInUseError:
            self.notificationRequested.emit(
                self.tr("Action Blocked"),
                self.tr("Cannot delete the profile that is currently in use."),
                "warning",
                3000,
            )
        except ProfileNotFoundError:
            self.notificationRequested.emit(
                self.tr("Error"),
                self.tr("Profile not found. It may have already been deleted."),
                "error",
                3000,
            )
