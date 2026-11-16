import {Video} from '@remotion/media';
import React from 'react';
import {AbsoluteFill, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {enveloppe} from '../outils';
import {COULEURS, TITRE, ZONE} from '../style';
import type {EffetDe} from '../types';

/** Phrase choc en très grand, mon visage flouté derrière, entrée en 3D. */
export const GrandTitre: React.FC<{e: EffetDe<'grand_titre'>; video: string}> = ({e, video}) => {
	const frame = useCurrentFrame(); // 0 = début du titre
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	const duree = e.fin - e.debut;
	const fond = enveloppe(t, 0, duree, 0.25, 0.3);
	const entree3d = interpolate(t, [0.05, 0.75], [0, 1], {
		extrapolateLeft: 'clamp',
		extrapolateRight: 'clamp',
		easing: Easing.spring({damping: 14, mass: 0.9}),
	});
	const sortie = interpolate(t, [duree - 0.3, duree], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

	const mots = e.texte.split(' ');
	const fort = (m: string) => !!e.motFort && e.motFort.toLowerCase().split(' ').includes(m.toLowerCase().replace(/[.,!?…]/g, ''));
	return (
		<AbsoluteFill>
			<AbsoluteFill style={{opacity: fond}}>
				{/* même vidéo, muette, fortement floutée et teintée bordeaux sombre */}
				<AbsoluteFill style={{scale: '1.15', filter: 'blur(38px) saturate(0.8)'}}>
					<Video src={staticFile(video)} trimBefore={Math.round(e.debut * fps)} muted objectFit="cover" />
				</AbsoluteFill>
				<AbsoluteFill style={{backgroundColor: COULEURS.bordeauxSombre, opacity: 0.62}} />
			</AbsoluteFill>
			<AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', perspective: 1400}}>
				<div
					style={{
						width: width - ZONE.gauche - ZONE.droite,
						textAlign: 'center',
						fontFamily: TITRE,
						fontWeight: 600,
						fontSize: 132,
						lineHeight: 1.04,
						color: COULEURS.blanc,
						textShadow: '0 6px 30px rgba(0,0,0,0.35)',
						rotate: `x ${interpolate(entree3d, [0, 1], [78, 0])}deg`,
						translate: `${(ZONE.gauche - ZONE.droite) / 2}px ${interpolate(entree3d, [0, 1], [120, 0])}px`,
						scale: String(interpolate(sortie, [0, 1], [1.06, 1]) * interpolate(entree3d, [0, 1], [0.85, 1])),
						opacity: Math.min(interpolate(entree3d, [0, 0.35], [0, 1], {extrapolateRight: 'clamp'}), sortie),
						transformOrigin: '50% 100%',
					}}
				>
					{mots.map((m, i) => (
						<span
							key={i}
							style={{
								fontStyle: fort(m) ? 'italic' : 'normal',
								color: fort(m) ? COULEURS.creme : undefined,
							}}
						>
							{m}
							{i < mots.length - 1 ? ' ' : ''}
						</span>
					))}
				</div>
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
