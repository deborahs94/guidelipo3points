import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux} from '../outils';
import {COULEURS, TEXTE, ZONE, teinte} from '../style';

/** Transition « lumière colorée » : deux halos chauds traversent l'image autour de la coupe. */
export const Lumiere: React.FC = () => {
	const frame = useCurrentFrame(); // la Sequence commence 0,45 s avant la coupe
	const {fps, width, height} = useVideoConfig();
	const u = frame / fps / 0.9; // 0 -> 1 sur 0,9 s
	const intensite = Math.sin(Math.PI * Math.min(1, Math.max(0, u)));
	return (
		<AbsoluteFill style={{mixBlendMode: 'screen', opacity: 0.75 * intensite}}>
			<div
				style={{
					position: 'absolute',
					width: width * 1.4,
					height: width * 1.4,
					left: interpolate(u, [0, 1], [-width * 0.9, width * 0.5]),
					top: interpolate(u, [0, 1], [height * 0.05, height * 0.35]),
					background: 'radial-gradient(circle, rgba(243,170,140,0.85) 0%, rgba(176,60,80,0.5) 35%, rgba(107,21,38,0) 70%)',
				}}
			/>
			<div
				style={{
					position: 'absolute',
					width: width * 1.1,
					height: width * 1.1,
					left: interpolate(u, [0, 1], [width * 0.6, -width * 0.3]),
					top: interpolate(u, [0, 1], [height * 0.6, height * 0.25]),
					background: 'radial-gradient(circle, rgba(255,228,196,0.7) 0%, rgba(255,200,160,0.3) 40%, rgba(255,200,160,0) 70%)',
				}}
			/>
			<AbsoluteFill style={{backgroundColor: COULEURS.creme, opacity: 0.18 * Math.pow(intensite, 4)}} />
		</AbsoluteFill>
	);
};

/** Léger grain de film (bruit SVG différent à chaque image). */
export const Grain: React.FC<{force: number}> = ({force}) => {
	const frame = useCurrentFrame();
	const {width, height} = useVideoConfig();
	return (
		<AbsoluteFill style={{opacity: force, mixBlendMode: 'overlay', pointerEvents: 'none'}}>
			<svg width={width} height={height}>
				<filter id="grain">
					<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} seed={frame % 97} stitchTiles="stitch" />
					<feColorMatrix type="saturate" values="0" />
				</filter>
				<rect width="100%" height="100%" filter="url(#grain)" />
			</svg>
		</AbsoluteFill>
	);
};

/** Barre de chapitres fine en haut (sous la zone réservée aux boutons). */
export const Chapitres: React.FC<{chapitres: {debut: number; titre: string}[]; duree: number; fondClair: boolean}> = ({
	chapitres,
	duree,
	fondClair,
}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	if (!chapitres.length) return null;
	const c = teinte(fondClair);
	const liste = [...chapitres].sort((a, b) => a.debut - b.debut);
	const courant = [...liste].reverse().find((ch) => t >= ch.debut) ?? liste[0];
	const debutCourant = courant.debut;
	const largeurTotale = width - ZONE.gauche - ZONE.droite;
	const entree = interpolate(t, [0, 0.5], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: doux});
	const changement = interpolate(t, [debutCourant, debutCourant + 0.35], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: doux,
	});
	return (
		<AbsoluteFill style={{opacity: entree}}>
			<div style={{position: 'absolute', top: ZONE.haut + 6, left: ZONE.gauche, width: largeurTotale, display: 'flex', gap: 10}}>
				{liste.map((ch, i) => {
					const fin = liste[i + 1]?.debut ?? duree;
					const rempli = interpolate(t, [ch.debut, fin], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
					return (
						<div
							key={i}
							style={{
								flex: fin - ch.debut,
								height: 6,
								borderRadius: 3,
								overflow: 'hidden',
								backgroundColor: fondClair ? 'rgba(24,24,24,0.14)' : 'rgba(255,255,255,0.28)',
							}}
						>
							<div style={{width: `${rempli * 100}%`, height: '100%', backgroundColor: c.accent}} />
						</div>
					);
				})}
			</div>
			<div
				style={{
					position: 'absolute',
					top: ZONE.haut + 28,
					left: ZONE.gauche,
					fontFamily: TEXTE,
					fontWeight: 600,
					fontSize: 22,
					letterSpacing: '0.3em',
					textTransform: 'uppercase',
					color: c.texte,
					textShadow: c.ombre,
					opacity: changement,
					translate: `0px ${interpolate(changement, [0, 1], [8, 0])}px`,
				}}
			>
				{courant.titre}
			</div>
		</AbsoluteFill>
	);
};
