"""PolarOps environment-driven Django settings."""
import os
from urllib.parse import urlparse
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-this-key')
DEBUG = os.getenv('DJANGO_DEBUG', '1') == '1'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',') if host.strip()]
if os.getenv('VERCEL') == '1':
 ALLOWED_HOSTS += ['.vercel.app']
 CSRF_TRUSTED_ORIGINS = ['https://*.vercel.app']
INSTALLED_APPS = [
 'django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles',
 'rest_framework','rest_framework.authtoken','simple_history',
 'accounts.apps.AccountsConfig','core','expeditions','personnel','assets','inventory','transport','risk','emergency','reports']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','simple_history.middleware.HistoryRequestMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'polarops.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages','core.context_processors.polar_theme']}}]
WSGI_APPLICATION = 'polarops.wsgi.application'
if os.getenv('DATABASE_URL'):
 database_url = urlparse(os.environ['DATABASE_URL'])
 DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':database_url.path.lstrip('/'),'USER':database_url.username,'PASSWORD':database_url.password,'HOST':database_url.hostname,'PORT':database_url.port or 5432,'CONN_MAX_AGE':60,'OPTIONS':{'sslmode':os.getenv('DB_SSLMODE','require')}}}
elif os.getenv('DB_ENGINE') == 'postgres':
 DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','polarops'),'USER':os.getenv('POSTGRES_USER','polarops'),'PASSWORD':os.getenv('POSTGRES_PASSWORD','polarops'),'HOST':os.getenv('POSTGRES_HOST','db'),'PORT':os.getenv('POSTGRES_PORT','5432')}}
else: DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
AUTH_PASSWORD_VALIDATORS = [{'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},{'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':10}},{'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'}]
LANGUAGE_CODE='en-us'; TIME_ZONE='UTC'; USE_I18N=True; USE_TZ=True
STATIC_URL='static/'; STATICFILES_DIRS=[BASE_DIR/'static']; STATIC_ROOT=BASE_DIR/'staticfiles'; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
MEDIA_URL='/media/'; MEDIA_ROOT=BASE_DIR/'media'; POLAROPS_PUBLIC_URL=os.getenv('POLAROPS_PUBLIC_URL','http://127.0.0.1:8000').rstrip('/')
LOGIN_URL='login'; LOGIN_REDIRECT_URL='dashboard'; LOGOUT_REDIRECT_URL='login'
REST_FRAMEWORK={'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.TokenAuthentication','rest_framework.authentication.SessionAuthentication'],'DEFAULT_PERMISSION_CLASSES':['accounts.permissions.PolarDRFPermission']}
