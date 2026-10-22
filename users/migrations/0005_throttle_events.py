# Hand-written: the autodetector can't pair a model rename with a field rename (drop + create).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_alter_user_email_user_users_email_ascii'),
    ]

    operations = [
        # RenameField leaves Index.fields stale, so the indexes are rebuilt.
        migrations.RemoveIndex(model_name='loginfailure', name='login_failures_digest_idx'),
        migrations.RemoveIndex(model_name='loginfailure', name='login_failures_ip_idx'),
        migrations.RenameModel(old_name='LoginFailure', new_name='ThrottleEvent'),
        migrations.RenameField(model_name='throttleevent', old_name='failed_at', new_name='created_at'),
        migrations.AlterModelTable(name='throttleevent', table='throttle_events'),
        migrations.AddField(
            model_name='throttleevent',
            name='scope',
            field=models.CharField(choices=[('login_failure', 'Login Failure'), ('password_reset', 'Password Reset'), ('signup', 'Signup'), ('verification_email', 'Verification Email')], default='login_failure', max_length=32),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='throttleevent',
            name='email_digest',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddIndex(
            model_name='throttleevent',
            index=models.Index(fields=['scope', 'email_digest', 'created_at'], name='throttle_events_digest_idx'),
        ),
        migrations.AddIndex(
            model_name='throttleevent',
            index=models.Index(fields=['scope', 'ip', 'created_at'], name='throttle_events_ip_idx'),
        ),
        migrations.AddConstraint(
            model_name='throttleevent',
            constraint=models.CheckConstraint(condition=models.Q(('scope__in', ['login_failure', 'password_reset', 'signup', 'verification_email'])), name='throttle_events_scope_valid', violation_error_message='Unknown throttle scope.'),
        ),
    ]
