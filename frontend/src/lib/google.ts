'use client';

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(options: { client_id: string; nonce: string; callback: (response: { credential: string }) => void }): void;
          prompt(callback?: (notification: { isNotDisplayed(): boolean; getNotDisplayedReason(): string }) => void): void;
        };
      };
    };
  }
}

let scriptPromise: Promise<void> | null = null;

function loadGoogleIdentityScript(): Promise<void> {
  if (window.google) return Promise.resolve();
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-energy-google-identity]');
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('Google sign-in could not be loaded.')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.dataset.energyGoogleIdentity = 'true';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('Google sign-in could not be loaded.'));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export async function requestGoogleCredential(clientId: string, nonce: string): Promise<string> {
  await loadGoogleIdentityScript();
  if (!window.google) throw new Error('Google sign-in is unavailable.');
  return new Promise((resolve, reject) => {
    let settled = false;
    window.google!.accounts.id.initialize({
      client_id: clientId,
      nonce,
      callback: (response) => {
        settled = true;
        resolve(response.credential);
      },
    });
    window.google!.accounts.id.prompt((notification) => {
      if (!settled && notification.isNotDisplayed()) {
        reject(new Error(`Google sign-in is unavailable (${notification.getNotDisplayedReason()}).`));
      }
    });
  });
}
