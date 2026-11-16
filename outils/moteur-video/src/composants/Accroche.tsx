import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import {doux, enveloppe} from '../outils';
import {COULEURS, TEXTE, TITRE, ZONE, teinte} from '../style';
import type {EffetDe} from '../types';

/** Curseur de largeur nulle : il suit la dernière lettre sans décaler le texte. */
const Curseur: React.FC<{visible: boolean; couleur: string}> = ({visible, couleur}) => (
	<span style={{position: 'relative', display: 'inline-block', width: 0}}>
		<span
			style={{
				position: 'absolute',
				left: 2,
				bottom: -12,
				width: 4,
				height: 86,
				backgroundColor: couleur,
				opacity: visible ? 0.9 : 0,
			}}
		/>
	</span>
);

/** Accroche d'ouverture : sur-titre en petites majuscules espacées + titre Playfair qui s'écrit lettre par lettre. */
export const Accroche: React.FC<{e: EffetDe<'accroche'>; fondClair: boolean}> = ({e, fondClair}) => {
	const frame = useCurrentFrame(); // 0 = début de l'accroche
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	const duree = e.fin - e.debut;
	const c = teinte(fondClair);
	const visible = enveloppe(t, 0, duree, 0.3, 0.3);

	// écriture lettre par lettre, terminée 0,8 s avant la fin
	const lettres = Array.from(e.titre);
	const finFrappe = Math.max(0.6, duree - 0.8);
	const nb = Math.floor(
		interpolate(t, [0.35, finFrappe], [0, lettres.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}),
	);
	// repérer les lettres du mot fort
	const idxFort = e.motFort ? e.titre.toLowerCase().indexOf(e.motFort.toLowerCase()) : -1;
	const estFort = (i: number) => idxFort >= 0 && i >= idxFort && i < idxFort + (e.motFort?.length ?? 0);
	const curseur = nb < lettres.length || Math.floor(t * 2.5) % 2 === 0;

	const surtitre = interpolate(t, [0, 0.35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: doux});
	return (
		<AbsoluteFill style={{opacity: visible}}>
			{/* voile doux en haut pour que le titre reste lisible sur les cheveux ou le décor */}
			<AbsoluteFill
				style={{
					height: 900,
					background: fondClair
						? 'linear-gradient(to bottom, rgba(248,246,241,0.92) 0%, rgba(248,246,241,0.75) 55%, rgba(248,246,241,0) 100%)'
						: 'linear-gradient(to bottom, rgba(24,24,24,0.6) 0%, rgba(24,24,24,0.35) 55%, rgba(24,24,24,0) 100%)',
				}}
			/>
			<div
				style={{
					position: 'absolute',
					top: ZONE.haut + 70,
					left: ZONE.gauche + 20,
					width: width - ZONE.gauche - ZONE.droite - 40,
					textAlign: 'center',
				}}
			>
				<div
					style={{
						fontFamily: TEXTE,
						fontWeight: 600,
						fontSize: 30,
						letterSpacing: '0.35em',
						textTransform: 'uppercase',
						color: fondClair ? COULEURS.bordeaux : COULEURS.creme,
						opacity: surtitre,
						translate: `0px ${interpolate(surtitre, [0, 1], [16, 0])}px`,
						textShadow: c.ombre,
					}}
				>
					{e.surtitre}
				</div>
				<div
					style={{
						margin: '22px auto 26px',
						width: interpolate(surtitre, [0, 1], [0, 90]),
						height: 2,
						backgroundColor: fondClair ? COULEURS.bordeaux : COULEURS.creme,
						opacity: 0.7,
					}}
				/>
				<div
					style={{
						fontFamily: TITRE,
						fontWeight: 600,
						fontSize: 96,
						lineHeight: 1.08,
						color: c.texte,
						textShadow: c.ombre,
					}}
				>
					{lettres.map((l, i) => (
						<React.Fragment key={i}>
							{i === nb ? <Curseur visible={curseur} couleur={c.accent} /> : null}
							<span
								style={{
									opacity: i < nb ? 1 : 0,
									fontStyle: estFort(i) ? 'italic' : 'normal',
									color: estFort(i) ? c.accent : undefined,
								}}
							>
								{l}
							</span>
						</React.Fragment>
					))}
					{nb >= lettres.length ? <Curseur visible={curseur} couleur={c.accent} /> : null}
				</div>
			</div>
		</AbsoluteFill>
	);
};
