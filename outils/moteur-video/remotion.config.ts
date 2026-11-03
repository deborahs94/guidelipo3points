import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setJpegQuality(92);
Config.setOverwriteOutput(true);

// Remotion ne peut pas télécharger son navigateur ici (site bloqué) :
// on utilise le Chromium headless déjà installé, sauf si REMOTION_CHROME en indique un autre.
Config.setBrowserExecutable(
	process.env.REMOTION_CHROME ??
		'/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell',
);
// Repli prévu si le rendu plante (« Target closed », « icudtl.dat ») : REMOTION_CHROME_MODE=chrome-for-testing
if (process.env.REMOTION_CHROME_MODE === 'chrome-for-testing') {
	Config.setChromeMode('chrome-for-testing');
}
