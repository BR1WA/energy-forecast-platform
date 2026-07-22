'use client';

import React, { useState, useEffect } from 'react';

export type Language = 'en' | 'fr' | 'ar';

type Translations = Record<string, string>;

const translations: Record<Language, Translations> = {
  en: {
    // Nav & Sidebar
    'nav.dashboard': 'Dashboard',
    'nav.forecasts': 'Forecasts',
    'nav.consumption': 'Consumption',
    'nav.simulation': 'Simulation',
    'nav.analytics': 'Analytics',
    'nav.alerts': 'Alerts',
    'nav.settings': 'Settings',
    'nav.admin': 'Admin Panel',
    'nav.profile': 'Profile',
    'nav.logout': 'Sign Out',
    'nav.telemetry': 'Live Telemetry',
    'nav.recommendations': 'Recommendations',
    'nav.budget': 'Budget & Goals',
    'nav.reports': 'Reports',

    // Dashboard
    'dashboard.title': 'Energy Forecast Dashboard',
    'dashboard.subtitle': 'Measured electricity, cost, freshness, and data coverage.',
    'dashboard.total_consumption': 'Total Consumption',
    'dashboard.peak_hours': 'Peak Hours',
    'dashboard.anomaly_status': 'Anomaly Status',
    'dashboard.forecasts_run': 'Forecasts Run',
    'dashboard.consumption_forecast': 'Energy Consumption & Forecast',
    'dashboard.recent_activity': 'Recent Forecast Activity',
    'dashboard.meter_connection': 'Smart Meter Connection',
    'dashboard.connected': 'Connected',
    'dashboard.disconnected': 'Disconnected',
    'dashboard.no_forecasts': 'No forecasts run yet. Go to the Forecaster tab to run your first prediction.',

    // Forecast
    'forecast.title': 'Energy Forecaster',
    'forecast.subtitle': 'Run predictions using state-of-the-art ML models.',
    'forecast.upload_file': 'Upload CSV',
    'forecast.smart_meter': 'Smart Meter',
    'forecast.model': 'Model',
    'forecast.target': 'Target Variable',
    'forecast.run_forecast': 'Run Prediction',
    'forecast.sync_meter': 'Sync Smart Meter',
    'forecast.historical': 'Historical (96h)',
    'forecast.prediction': 'Prediction (24h)',
    'forecast.metrics': 'Prediction Metrics',
    'forecast.r2': 'R² Score',
    'forecast.rmse': 'RMSE',
    'forecast.mae': 'MAE',
    'forecast.mape': 'MAPE',

    // Analytics
    'analytics.title': 'Advanced Analytics',
    'analytics.subtitle': 'Decompose and analyze historical consumption patterns.',
    'analytics.export': 'Export Report (PDF)',
    'analytics.patterns': 'Consumption Patterns',
    'analytics.load_curve': 'Average Load Curve',
    'analytics.anomalies': 'Anomaly Log',

    // Alerts
    'alerts.title': 'Alerts & Load Shifting',
    'alerts.subtitle': 'Real-time notifications and grid load optimization recommendations.',
    'alerts.recommendations': 'Load-Shifting Recommendations',
    'alerts.active_alerts': 'Active Alerts',
    'alerts.realtime_logs': 'Real-Time Alert Feed',

    // Settings
    'settings.title': 'Account Settings',
    'settings.subtitle': 'Manage your profile, preferences, and security settings.',
    'settings.preferences': 'Preferences',
    'settings.security': 'Security',
    'settings.display': 'Display & Language',
    'settings.display_desc': 'Customize how the platform looks and speaks.',
    'settings.theme': 'Theme Preference',
    'settings.theme_light': 'Light',
    'settings.theme_dark': 'Dark',
    'settings.theme_system': 'System',
    'settings.language': 'Language Selection',
    'settings.language_desc': 'Choose your preferred language. Layout mirrors for Arabic.',
    'settings.save': 'Save Preferences',
    'settings.password_title': 'Security Settings',
    'settings.password_desc': 'Manage your password and account security.',
    'settings.current_password': 'Current Password',
    'settings.new_password': 'New Password',
    'settings.confirm_password': 'Confirm New Password',
    'settings.update_password': 'Update Password',

    // Admin
    'admin.title': 'Admin Control Panel',
    'admin.subtitle': 'Manage user access and inspect release readiness.',
    'admin.users': 'User Management',
    'admin.email': 'Email',
    'admin.role': 'Role',
    'admin.activity': 'Last Activity',
  },
  fr: {
    // Nav & Sidebar
    'nav.dashboard': 'Tableau de bord',
    'nav.forecasts': 'Prévisions',
    'nav.consumption': 'Consommation',
    'nav.simulation': 'Simulation',
    'nav.analytics': 'Analyses',
    'nav.alerts': 'Alertes',
    'nav.settings': 'Paramètres',
    'nav.admin': 'Panel Admin',
    'nav.profile': 'Profil',
    'nav.logout': 'Déconnexion',
    'nav.telemetry': 'Télémesure Live',
    'nav.recommendations': 'Recommandations',
    'nav.budget': 'Budget et Objectifs',
    'nav.reports': 'Rapports',

    // Dashboard
    'dashboard.title': 'Tableau de bord énergétique',
    'dashboard.subtitle': 'Électricité mesurée, coût, fraîcheur et couverture des données.',
    'dashboard.total_consumption': 'Consommation Totale',
    'dashboard.peak_hours': 'Heures de Pointe',
    'dashboard.anomaly_status': 'Statut des Anomalies',
    'dashboard.forecasts_run': 'Prévisions Exécutées',
    'dashboard.consumption_forecast': 'Consommation d\'Énergie & Prévisions',
    'dashboard.recent_activity': 'Activité Récente de Prévision',
    'dashboard.meter_connection': 'Connexion Compteur Intelligent',
    'dashboard.connected': 'Connecté',
    'dashboard.disconnected': 'Déconnecté',
    'dashboard.no_forecasts': 'Aucune prévision exécutée. Accédez à l\'onglet Prévisions pour lancer votre première prédiction.',

    // Forecast
    'forecast.title': 'Prévisions Énergétiques',
    'forecast.subtitle': 'Exécutez des prédictions à l\'aide de modèles ML de pointe.',
    'forecast.upload_file': 'Importer CSV',
    'forecast.smart_meter': 'Compteur Intelligent',
    'forecast.model': 'Modèle',
    'forecast.target': 'Variable Cible',
    'forecast.run_forecast': 'Exécuter la Prédiction',
    'forecast.sync_meter': 'Synchroniser Linky',
    'forecast.historical': 'Historique (96h)',
    'forecast.prediction': 'Prédiction (24h)',
    'forecast.metrics': 'Métriques de Prédiction',
    'forecast.r2': 'Score R²',
    'forecast.rmse': 'RMSE',
    'forecast.mae': 'MAE',
    'forecast.mape': 'MAPE',

    // Analytics
    'analytics.title': 'Analyses Avancées',
    'analytics.subtitle': 'Décomposer et analyser les profils de consommation historique.',
    'analytics.export': 'Exporter Rapport (PDF)',
    'analytics.patterns': 'Profils de Consommation',
    'analytics.load_curve': 'Courbe de Charge Moyenne',
    'analytics.anomalies': 'Journal des Anomalies',

    // Alerts
    'alerts.title': 'Alertes & Effacement',
    'alerts.subtitle': 'Notifications en temps réel et recommandations d\'optimisation de charge.',
    'alerts.recommendations': 'Recommandations de Report de Charge',
    'alerts.active_alerts': 'Alertes Actives',
    'alerts.realtime_logs': 'Flux d\'Alertes en Temps Réel',

    // Settings
    'settings.title': 'Paramètres du Compte',
    'settings.subtitle': 'Gérez votre profil, vos préférences et vos paramètres de sécurité.',
    'settings.preferences': 'Préférences',
    'settings.security': 'Sécurité',
    'settings.display': 'Affichage & Langue',
    'settings.display_desc': 'Personnalisez l\'apparence et la langue de la plateforme.',
    'settings.theme': 'Préférence de Thème',
    'settings.theme_light': 'Clair',
    'settings.theme_dark': 'Sombre',
    'settings.theme_system': 'Système',
    'settings.language': 'Choix de la Langue',
    'settings.language_desc': 'Choisissez votre langue préférée. L\'affichage s\'inverse pour l\'arabe.',
    'settings.save': 'Enregistrer les Préférences',
    'settings.password_title': 'Paramètres de Sécurité',
    'settings.password_desc': 'Gérez votre mot de passe et la sécurité de votre compte.',
    'settings.current_password': 'Mot de passe actuel',
    'settings.new_password': 'Nouveau mot de passe',
    'settings.confirm_password': 'Confirmer le mot de passe',
    'settings.update_password': 'Mettre à jour le mot de passe',

    // Admin
    'admin.title': 'Panel de Contrôle Admin',
    'admin.subtitle': 'Gérer les accès utilisateurs et vérifier l’état de la version.',
    'admin.users': 'Gestion des Utilisateurs',
    'admin.email': 'Email',
    'admin.role': 'Rôle',
    'admin.activity': 'Dernière Activité',
  },
  ar: {
    // Nav & Sidebar
    'nav.dashboard': 'لوحة التحكم',
    'nav.forecasts': 'التنبؤات',
    'nav.consumption': 'الاستهلاك',
    'nav.simulation': 'المحاكاة',
    'nav.analytics': 'التحليلات',
    'nav.alerts': 'التنبيهات',
    'nav.settings': 'الإعدادات',
    'nav.admin': 'لوحة المشرف',
    'nav.profile': 'الملف الشخصي',
    'nav.logout': 'تسجيل الخروج',
    'nav.telemetry': 'القياس المباشر',
    'nav.recommendations': 'توصيات',
    'nav.budget': 'الميزانية والأهداف',
    'nav.reports': 'التقارير',

    // Dashboard
    'dashboard.title': 'لوحة التنبؤ بالطاقة',
    'dashboard.subtitle': 'المراقبة في الوقت الفعلي والتنبؤات المتقدمة للتعلم الآلي.',
    'dashboard.total_consumption': 'إجمالي الاستهلاك',
    'dashboard.peak_hours': 'ساعات الذروة',
    'dashboard.anomaly_status': 'حالة الشذوذ',
    'dashboard.forecasts_run': 'التنبؤات المنفذة',
    'dashboard.consumption_forecast': 'استهلاك الطاقة والتنبؤ',
    'dashboard.recent_activity': 'نشاط التنبؤ الأخير',
    'dashboard.meter_connection': 'اتصال العداد الذكي',
    'dashboard.connected': 'متصل',
    'dashboard.disconnected': 'غير متصل',
    'dashboard.no_forecasts': 'لم يتم تشغيل أي تنبؤات بعد. انتقل إلى تبويب التنبؤات لتشغيل أول تنبؤ لك.',

    // Forecast
    'forecast.title': 'متنبئ الطاقة',
    'forecast.subtitle': 'شغّل التنبؤات باستخدام نماذج التعلم الآلي الأحدث.',
    'forecast.upload_file': 'تحميل ملف CSV',
    'forecast.smart_meter': 'العداد الذكي',
    'forecast.model': 'النموذج',
    'forecast.target': 'المتغير المستهدف',
    'forecast.run_forecast': 'تشغيل التنبؤ',
    'forecast.sync_meter': 'مزامنة العداد الذكي',
    'forecast.historical': 'تاريخي (96 ساعة)',
    'forecast.prediction': 'توقع (24 ساعة)',
    'forecast.metrics': 'مقاييس التنبؤ',
    'forecast.r2': 'مقياس R²',
    'forecast.rmse': 'RMSE',
    'forecast.mae': 'MAE',
    'forecast.mape': 'MAPE',

    // Analytics
    'analytics.title': 'التحليلات المتقدمة',
    'analytics.subtitle': 'تحليل وتفكيك أنماط الاستهلاك التاريخية.',
    'analytics.export': 'تصدير التقرير (PDF)',
    'analytics.patterns': 'أنماط الاستهلاك',
    'analytics.load_curve': 'منحنى الحمل المتوسط',
    'analytics.anomalies': 'سجل الشذوذ',

    // Alerts
    'alerts.title': 'التنبيهات وترحيل الأحمال',
    'alerts.subtitle': 'التنبيهات الفورية وتوصيات تحسين حمل الشبكة.',
    'alerts.recommendations': 'توصيات ترحيل الأحمال',
    'alerts.active_alerts': 'التنبيهات النشطة',
    'alerts.realtime_logs': 'موجز التنبيهات الفورية',

    // Settings
    'settings.title': 'إعدادات الحساب',
    'settings.subtitle': 'إدارة ملفك الشخصي وتفضيلاتك وإعدادات الأمان.',
    'settings.preferences': 'التفضيلات',
    'settings.security': 'الأمان',
    'settings.display': 'العرض واللغة',
    'settings.display_desc': 'تخصيص مظهر المنصة ولغتها.',
    'settings.theme': 'تفضيل السمة',
    'settings.theme_light': 'فاتح',
    'settings.theme_dark': 'داكن',
    'settings.theme_system': 'النظام',
    'settings.language': 'اختيار اللغة',
    'settings.language_desc': 'اختر لغتك المفضلة. يتم عكس التنسيق للغة العربية.',
    'settings.save': 'حفظ التفضيلات',
    'settings.password_title': 'إعدادات الأمان',
    'settings.password_desc': 'إدارة كلمة المرور وأمان حسابك.',
    'settings.current_password': 'كلمة المرور الحالية',
    'settings.new_password': 'كلمة المرور الجديدة',
    'settings.confirm_password': 'تأكيد كلمة المرور الجديدة',
    'settings.update_password': 'تحديث كلمة المرور',

    // Admin
    'admin.title': 'لوحة تحكم المسؤول',
    'admin.subtitle': 'إدارة وصول المستخدمين والتحقق من جاهزية الإصدار.',
    'admin.users': 'إدارة المستخدمين',
    'admin.email': 'البريد الإلكتروني',
    'admin.role': 'الدور',
    'admin.activity': 'النشاط الأخير',
  }
};

interface I18nContextType {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
  isRTL: boolean;
}

const I18nContext = React.createContext<I18nContextType | undefined>(undefined);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<Language>('en');

  const updateDirection = (lang: Language) => {
    const dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.documentElement.dir = dir;
    if (lang === 'ar') {
      document.documentElement.classList.add('rtl-active');
    } else {
      document.documentElement.classList.remove('rtl-active');
    }
  };

  // Load saved language on mount
  useEffect(() => {
    const saved = localStorage.getItem('pfe_language') as Language;
    if (saved && ['en', 'fr', 'ar'].includes(saved)) {
      setLanguageState(saved);
      updateDirection(saved);
    }
  }, []);

  const setLanguage = (lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem('pfe_language', lang);
    updateDirection(lang);
  };

  const t = (key: string): string => {
    return translations[language][key] || translations['en'][key] || key;
  };

  const isRTL = language === 'ar';

  return (
    <I18nContext.Provider value={{ language, setLanguage, t, isRTL }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = () => {
  const context = React.useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
};
