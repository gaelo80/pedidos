# gestion_inventario/settings.py
import os
from pathlib import Path
from decouple import config
from dotenv import load_dotenv

load_dotenv()

    # Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

CONTRASEÑA_PARA_VERIFICAR_PEDIDO = "Nohelia123F"

DEBUG = os.getenv('DEBUG', 'True') == 'True'

if DEBUG:
    # --- CONFIGURACIÓN PARA DESARROLLO ---
    # Los archivos de medios (fotos de productos) SÍ van a R2.
    # Los archivos estáticos (CSS/JS del admin) se sirven localmente.
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage", # <-- Usa el sistema local
        },
    }
else:
    # --- CONFIGURACIÓN PARA PRODUCCIÓN ---
    # TODO va a R2.
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
    }

# Credenciales para Boto3 (la librería que habla con R2)
AWS_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('R2_BUCKET_NAME')

# --- ¡ESTA PARTE ES CRÍTICA PARA R2! ---
# Le decimos a Boto3 que no vaya a Amazon, sino a Cloudflare.
AWS_S3_ENDPOINT_URL = f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com"

# Un dominio personalizado para servir los archivos (opcional pero muy recomendado)
# Por ejemplo, si configuras 'media.tuapp.com' para apuntar a tu bucket.
# AWS_S3_CUSTOM_DOMAIN = 'media.tuapp.com' 
# Si no tienes dominio personalizado, puedes construir la URL manualmente en el modelo/vista.

AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400', # Cachear archivos por 24 horas
}

# Otras configuraciones importantes
AWS_DEFAULT_ACL = 'public-read' # Hace los archivos públicamente visibles por defecto
AWS_S3_REGION_NAME = 'auto' # R2 requiere 'auto'
AWS_S3_SIGNATURE_VERSION = 's3v4'
# --- FIN DE LA CONFIGURACIÓN DE R2 ---

SITE_ID = 1

    # Quick-start development settings - unsuitable for production
    # See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

    # SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

    # SECURITY WARNING: don't run with debug turned on in production!
#DEBUG = config('DEBUG', default=False, cast=bool)

#ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost' 'empresa-prueba.localhost').split(',')
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.localhost']
                 #pedidosluisferry.store', 'www.pedidosluisferry.store', '168.231.93.109']

CSRF_TRUSTED_ORIGINS = [
   # 'https://5fe8-148-222-225-228.ngrok-free.app'
    # Puedes añadir otros orígenes de confianza aquí si los tienes,
    # por ejemplo, el dominio de tu sitio en producción.
]


CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5" 
CRISPY_TEMPLATE_PACK = "bootstrap5"          

INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.humanize',
        'django.contrib.sites',
        
    
        
        # MIS APPS
        'core.apps.CoreConfig',
        'productos',
        'clientes',
        'vendedores',
        'bodega.apps.BodegaConfig',
        'cartera',
        'factura',
        'pedidos',
        'devoluciones',
        'informes',
        'catalogo',
        'user_management',
        
        # APLICACIONES DE TERCERO
        'rest_framework',
        'rest_framework.authtoken',
        'rest_framework_simplejwt',
        'django_extensions',
        'import_export',      
        'crispy_forms',  
        'crispy_bootstrap5',
        'widget_tweaks',
        'bootstrap4',
       
    ]

MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
        'core.middleware.TenantMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.locale.LocaleMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]

ROOT_URLCONF = 'gestion_inventario.urls'

TEMPLATES = [
        {
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [BASE_DIR / 'templates'],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.debug',
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                    'django.contrib.messages.context_processors.messages',
                    'core.context_processors.empresa_context',
                ],
            },
        },
    ]

WSGI_APPLICATION = 'gestion_inventario.wsgi.application'
CRISPY_TEMPLATE_PACK = 'bootstrap4'


    # Database
    # https://docs.djangoproject.com/en/5.1/ref/settings/#databases
   
   
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
        'USER': config('DB_USER', default=''),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default=''),
        'PORT': config('DB_PORT', default=''),
    }
}


AUTH_PASSWORD_VALIDATORS = [
        {
            'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
        },
        {
            'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
        },
    ]

AUTH_USER_MODEL = 'core.User'

    # Internationalization
    # https://docs.djangoproject.com/en/5.1/topics/i18n/

    # Cambiar a español si prefieres la interfaz de Django en español
    # LANGUAGE_CODE = 'es-co' # Ejemplo para Colombia
LANGUAGE_CODE = 'es-co'

TIME_ZONE = 'America/Bogota' # Considera cambiar a tu zona horaria, ej: 'America/Bogota'

USE_I18N = True

USE_TZ = True # Mantener True es importante para manejar zonas horarias


    # Static files (CSS, JavaScript, Images)
    # https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # Cambia esto si usas un servidor diferente para producción
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

    # Aquí añadirías STATIC_ROOT para producción más adelante


    # Default primary key field type
    # https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


    # --- CONFIGURACIÓN DE DJANGO REST FRAMEWORK --- ### AÑADIDO AQUÍ ###
REST_FRAMEWORK = {
        'DEFAULT_AUTHENTICATION_CLASSES': [
            # Indica a DRF que use TokenAuthentication por defecto para las vistas de API
            'rest_framework_simplejwt.authentication.JWTAuthentication',
            # Comentamos SessionAuthentication para evitar conflictos con Postman/APIs
            'rest_framework.authentication.SessionAuthentication',
        ],
        'DEFAULT_PERMISSION_CLASSES': [
            # Requiere que el usuario esté autenticado para acceder a cualquier endpoint por defecto
            'rest_framework.permissions.IsAuthenticated',
        ]
    }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}


LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = 'login'