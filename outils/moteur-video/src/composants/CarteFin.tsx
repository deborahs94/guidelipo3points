import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux} from '../outils';
import {COULEURS, TEXTE, TITRE} from '../style';
import type {EffetDe} from '../types';

/** Carte de fin sur fond crème : nom en Playfair italique bordeaux, trait fin, compte en petites majuscules. */
export const CarteFin: React.FC<{e: EffetDe<'fin'>}> = ({e}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const t = frame / fps;
	const etape = (debut: number) =>
		interpolate(t, [debut, debut + 0.45], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: doux});
	const fond = etape(0);
	const petit: React.CSSProperties = {
		fontFamily: TEXTE,
		fontWeight: 600,
		fontSize: 28,
		letterSpacing: '0.35em',
		textTransform: 'uppercase',
		color: COULEURS.noir,
	};
	return (
		<AbsoluteFill style={{backgroundColor: COULEURS.creme, opacity: fond, justifyContent: 'center', alignItems: 'center'}}>
			<div style={{textAlign: 'center', translate: '-40px -60px'}}>
				<div style={{...petit, opacity: etape(0.15)}}>{e.sousTitre ?? 'Esthéticienne · Formatrice'}</div>
				<div
					style={{
						fontFamily: TITRE,
						fontStyle: 'italic',
						fontWeight: 600,
						fontSize: 170,
						lineHeight: 1.1,
						color: COULEURS.bordeaux,
						marginTop: 24,
						opacity: etape(0.3),
						translate: `0px ${interpolate(etape(0.3), [0, 1], [26, 0])}px`,
					}}
				>
					{e.nom ?? 'Déborah'}
				</div>
				<div
					style={{
						width: 2,
						height: 90 * etape(0.55),
						backgroundColor: COULEURS.bordeaux,
						opacity: 0.6,
						margin: '26px auto',
					}}
				/>
				<div style={{...petit, fontSize: 26, opacity: etape(0.7)}}>{e.compte ?? '@deborah.s.liporf94'}</div>
				{e.motCle ? (
					<div style={{marginTop: 46, opacity: etape(0.9)}}>
						<div style={{...petit, fontSize: 24}}>Écris</div>
						<div style={{fontFamily: TITRE, fontStyle: 'italic', fontSize: 90, color: COULEURS.bordeaux}}>{e.motCle}</div>
						<div style={{...petit, fontSize: 24}}>en commentaire</div>
					</div>
				) : null}
			</div>
		</AbsoluteFill>
	);
};
