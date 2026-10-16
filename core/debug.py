import re

from django.views.debug import SafeExceptionReporterFilter


class BrokerSafeExceptionReporterFilter(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        f"{SafeExceptionReporterFilter.hidden_settings.pattern}|BROKER_URL", flags=re.I
    )
