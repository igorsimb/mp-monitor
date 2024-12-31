from django.core.management.base import BaseCommand
from accounts.models import User, Profile


class Command(BaseCommand):
    help = 'Create profiles for existing users'

    def handle(self, *args, **kwargs):
        users_without_profiles = User.objects.exclude(profile__isnull=False)
        total_created = 0

        for user in users_without_profiles:
            profile, created = Profile.objects.get_or_create(user=user)
            if created:
                total_created += 1
                self.stdout.write(self.style.SUCCESS(f'Profile created for user: {user.username}'))

        # Summary output
        if total_created > 0:
            self.stdout.write(self.style.SUCCESS(f'Total profiles created: {total_created}'))
        else:
            self.stdout.write(self.style.WARNING('No new profiles were created. All users already have profiles.'))
