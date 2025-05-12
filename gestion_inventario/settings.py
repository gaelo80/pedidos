# gestion_inventario/settings.py
import os
from dotenv import load_dotenv
import dj_database_url
from pathlib import Path

    # Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(os.path.join(BASE_DIR, '.env'))


    # Quick-start development settings - unsuitable for production
    # See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

    # SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

    # SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True' 

#allowed_hosts_str = os.getenv('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = ['pedidosluisferry.store', 'www.pedidosluisferry.store', '168.231.93.109']
                 
                 #pedidosluisferry.store', 'www.pedidosluisferry.store', '168.231.93.109']

CSRF_TRUSTED_ORIGINS = [
   # 'https://5fe8-148-222-225-228.ngrok-free.app'
    # Puedes añadir otros orígenes de confianza aquí si los tienes,
    # por ejemplo, el dominio de tu sitio en producción.
]


    # Application definition

INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'django.contrib.humanize',
        
        

        # APLICACIONES DE TERCERO
        'rest_framework',
        'rest_framework.authtoken',
        'rest_framework_simplejwt',
        'django_extensions',
        'import_export',

        # MIS APPS
        'inventario.apps.InventarioConfig',
       
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
    'default': {
        # Comenta o elimina estas líneas de SQLite:
        # 'ENGINE': 'django.db.backends.sqlite3',
        # 'NAME': BASE_DIR / 'db.sqlite3',

        # Añade o descomenta estas líneas para MariaDB:
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'db_base',          # El nombre de la BD que creaste
        'USER': 'root',             # El usuario que creaste
        'PASSWORD': 'Echeverry..123@@##',   # La contraseña que estableciste para ese usuario
        'HOST': 'localhost',                    # O '127.0.0.1' (donde corre tu MariaDB)
        'PORT': '3306',                         # El puerto por defecto de MariaDB/MySQL
        'OPTIONS': {
            'init_command': "SET default_storage_engine=INNODB, sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
    }
}
    


    # Password validation
    # https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

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
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
    # --- FIN DE LA SECCIÓN REST_FRAMEWORK ---
