import PublicPolicyLayout from '@/components/public-policy-layout';


export default function PrivacyPage() {
  return (
    <PublicPolicyLayout title="Privacy notice">
      <section><h2 className="text-lg font-semibold text-white">Data we process</h2><p className="mt-2">EnergyAI processes your account profile, site and tariff configuration, meter metadata and readings, forecasts, alerts, recommendations, and security-relevant account events to provide the service.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Why it is used</h2><p className="mt-2">The data is used to authenticate you, ingest and display owned energy measurements, generate the requested forecasts and reports, evaluate configured alert rules, deliver opted-in transactional messages, and protect account integrity.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Storage and disclosure</h2><p className="mt-2">Account data is stored in the configured application database and durable avatar storage. Email and Google providers receive only the information required for the enabled operation. EnergyAI does not claim to sell personal data.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Your controls</h2><p className="mt-2">Settings provides a machine-readable export and irreversible account deletion. Exports exclude passwords, session and action-token hashes, meter ingestion secrets, provider credentials, and other users’ data.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Retention and security</h2><p className="mt-2">Owned product data is removed when the account is deleted. A minimal anonymized deletion event may be retained to evidence the security operation. Backup retention and access are governed by the deployment operator’s documented policy.</p></section>
    </PublicPolicyLayout>
  );
}
