# gestion_inventario/settings.py
import os
from pathlib import Path
from decouple import config

    # Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

CONTRASEÑA_PARA_VERIFICAR_PEDIDO = "Nohelia123F"
SITE_ID = 1

    # Quick-start development settings - unsuitable for production
    # See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

    # SECURITY WARNING: keep the secret key used in production secret!
import os
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-%lazc!2vk9ln-$2nk!vav2=iyulutxfab(i9dxdk^p*j=ofl')

    # SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = ['www.pedidoslouisferry.online', 'pedidoslouisferry.online', '168.231.93.109']
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
        'core',
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
       
    ]

MIDDLEWARE = [
        'django.middleware.security.SecurityMiddleware',
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
                ],
            },
        },
    ]

WSGI_APPLICATION = 'gestion_inventario.wsgi.application'


    # Database
    # https://docs.djangoproject.com/en/5.1/ref/settings/#databases
   
   
DATABASES = {
    'default': {} # Iniciar como un diccionario vacío
}

# Obtener los valores de las variables de entorno una vez
DB_NAME_FROM_ENV = config('DB_NAME', default=None)
DB_ENGINE_FROM_ENV = config('DB_ENGINE', default=None)

if DB_NAME_FROM_ENV and DB_ENGINE_FROM_ENV == 'django.db.backends.mysql':
    # Configuración específica para MariaDB/MySQL
    DATABASES['default'] = {
        'ENGINE': DB_ENGINE_FROM_ENV,
        'NAME': DB_NAME_FROM_ENV,
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='3306'), # Puerto por defecto de MySQL/MariaDB
        'OPTIONS': {
            'charset': 'utf8mb4', # Opción específica para MySQL/MariaDB
        },
    }
elif DB_NAME_FROM_ENV and DB_ENGINE_FROM_ENV == 'django.db.backends.postgresql':
    # Configuración específica para PostgreSQL (ejemplo, si cambias en el futuro)
    DATABASES['default'] = {
        'ENGINE': DB_ENGINE_FROM_ENV,
        'NAME': DB_NAME_FROM_ENV,
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'), # Puerto por defecto de PostgreSQL
        # PostgreSQL no suele necesitar 'charset' en OPTIONS aquí
    }
else:
    # Configuración para SQLite por defecto (si no se definen DB_NAME y DB_ENGINE para MariaDB/MySQL)
    # O si DB_ENGINE no es uno de los conocidos
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # SQLite no usa USER, PASSWORD, HOST, PORT, ni la opción 'charset' en settings.py
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