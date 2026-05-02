"""
URL configuration for src project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from core.payments.stripe_webhook import stripe_webhook
from core.payments.CreateCheckSession import CreateCheckoutSessionView

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('api/', include('core.urls')),   # ← закрывающая скобка!
                  path('api/payments/create-checkout/', CreateCheckoutSessionView.as_view(), name='create_checkout'),
                  path('api/payments/stripe/webhook/',  stripe_webhook, name='stripe_webhook'),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
