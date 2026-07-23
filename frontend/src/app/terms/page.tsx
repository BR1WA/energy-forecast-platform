import PublicPolicyLayout from '@/components/public-policy-layout';


export default function TermsPage() {
  return (
    <PublicPolicyLayout title="Terms of service">
      <section><h2 className="text-lg font-semibold text-white">Service scope</h2><p className="mt-2">EnergyAI provides one-site electricity monitoring, fixed-horizon forecasting, evidence-backed alerting, recommendations, reports, and account controls according to the capabilities currently shown by the application.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Informational outputs</h2><p className="mt-2">Forecasts, alerts, costs, and recommendations are informational. They do not replace qualified electrical, safety, emergency, billing, or financial advice and do not provide device-control capability.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Account responsibilities</h2><p className="mt-2">Provide accurate configuration, protect passwords and meter keys, review imported data before use, and do not attempt to access another account or disrupt the service.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Availability and changes</h2><p className="mt-2">Optional providers and the 168-hour forecast may be unavailable when disabled or unhealthy. Material terms changes must be published with a new effective date by the service owner.</p></section>
      <section><h2 className="text-lg font-semibold text-white">Account termination</h2><p className="mt-2">You may permanently delete your account from Settings after recent authentication. Deletion cannot be undone; retain an export first if you need a copy.</p></section>
    </PublicPolicyLayout>
  );
}
