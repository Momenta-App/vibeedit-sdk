const button = document.querySelector('#copy');
const handoff = document.querySelector('#handoff');
const feedback = document.querySelector('#copy-status');
async function loadRelease() {
  const response = await fetch('/agent-package/release.json', { cache: 'no-store' });
  if (!response.ok) return;
  const release = await response.json();
  if (release.schemaVersion !== 'vibeedit.publicRelease.v1' || release.status !== 'released') return;
  if (!/^\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?$/.test(release.npmVersion) || !/^\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?$/.test(release.pythonVersion)) return;
  const archive = /^https:\/\/github\.com\/Momenta-App\/vibeedit-sdk\/releases\/download\/v[0-9A-Za-z.\-]+\/release-manifest\.json$/;
  const skill = /^https:\/\/raw\.githubusercontent\.com\/Momenta-App\/vibeedit-sdk\/[a-f0-9]{40}\/skills\/vibeedit-setup\/SKILL\.md$/;
  if (!archive.test(release.manifestUrl) || !skill.test(release.setupSkillUrl) || !/^[a-f0-9]{64}$/.test(release.manifestSha256) || !/^[a-f0-9]{64}$/.test(release.setupSkillSha256) || !/^[a-f0-9]{40}$/.test(release.sourceRevision)) return;
  if (release.setupSkillUrl !== `https://raw.githubusercontent.com/Momenta-App/vibeedit-sdk/${release.sourceRevision}/skills/vibeedit-setup/SKILL.md` || release.manifestUrl !== `https://github.com/Momenta-App/vibeedit-sdk/releases/download/v${release.npmVersion}/release-manifest.json`) return;
  handoff.textContent = `Install VibeEdit for this project using the exact release manifest:
${release.manifestUrl}
Manifest SHA-256: ${release.manifestSha256}
Read its source-pinned setup skill (${release.setupSkillUrl}; SHA-256 ${release.setupSkillSha256}), verify the release artifacts, then help me make an editable video. Ask for my footage and creative direction. Keep credentials private and quote any paid operation before submitting it.`;
  for (const link of document.querySelectorAll('a[href]')) {
    const prefix = 'https://github.com/Momenta-App/vibeedit-sdk/blob/agent-package-launch/';
    if (link.href.startsWith(prefix)) link.href = `https://github.com/Momenta-App/vibeedit-sdk/blob/${release.sourceRevision}/${link.href.slice(prefix.length)}`;
  }
  document.querySelector('#release-status').textContent = 'Agent package release';
  document.querySelector('#versions').textContent = `Python ${release.pythonVersion} · npm ${release.npmVersion}`;
  button.disabled = false;
  button.textContent = 'Copy handoff';
}
button.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(handoff.textContent); feedback.textContent = 'Copied. Paste it into your agent.'; }
  catch { const range = document.createRange(); range.selectNodeContents(handoff); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range); feedback.textContent = 'Select and copy the handoff above.'; }
});
loadRelease().catch(() => { feedback.textContent = 'Release information is unavailable. Check the qualification link below.'; });
