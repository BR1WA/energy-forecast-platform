import PublicPolicyLayout from '@/components/public-policy-layout';


export default function SupportPage() {
  return (
    <PublicPolicyLayout contact="support" title="Support">
      <section><h2 className="text-lg font-semibold text-white">Requesting help</h2><p className="mt-2">Include the time of the issue, affected page, browser version, and any visible request identifier. Never send passwords, refresh tokens, action links, Google credentials, SMTP credentials, or meter ingestion keys.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Account and data requests</h2><p className="mt-2">Use the verification and password-reset journeys for access recovery. Use Settings for account export or deletion. Support cannot recover a deleted account or reveal stored credential hashes.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Safety and outages</h2><p className="mt-2">For electrical danger or emergency conditions, contact the appropriate qualified local service rather than relying on this application. During provider outages, in-app alerts and committed product data remain authoritative while email delivery retries independently.</p></section>
    </PublicPolicyLayout>
  );
}
