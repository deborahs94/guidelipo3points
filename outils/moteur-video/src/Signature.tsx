import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {Accroche} from './composants/Accroche';
import {Chapitres, Grain, Lumiere} from './composants/Ambiance';
import {Carte} from './composants/Carte';
import {CarteFin} from './composants/CarteFin';
import {Compteur} from './composants/Compteur';
import {GrandTitre} from './composants/GrandTitre';
import {Icone} from './composants/Icone';
import {Plan} from './composants/Plan';
import {Musique, Sons} from './composants/Sons';
import {SousTitres} from './composants/SousTitres';
import {actif} from './outils';
import {COULEURS} from './style';
import type {Effet, Props} from './types';

/** Compose toute la vidéo à partir de props.json (préparé depuis effets.json). */
export const Signature: React.FC<Props> = (p) => {
	const {fps} = useVideoConfig();
	const seq = (e: Effet) => ({from: Math.round(e.debut * fps), durationInFrames: Math.max(1, Math.round((e.fin - e.debut) * fps))});
	const de = <T extends Effet['type']>(type: T) => p.effets.filter((e): e is Extract<Effet, {type: T}> => e.type === type);
	// pas de sous-titres pendant les grands titres, les cartes et la carte de fin
	const masque = (t: number) => actif(p.effets, ['grand_titre', 'carte', 'fin'], t);

	return (
		<AbsoluteFill style={{backgroundColor: COULEURS.creme}}>
			<Plan p={p} />
			{de('carte').map((e, i) => (
				<Sequence key={`c${i}`} {...seq(e)} name={`Carte ${e.contenu}`}>
					<Carte e={e} />
				</Sequence>
			))}
			{de('grand_titre').map((e, i) => (
				<Sequence key={`g${i}`} {...seq(e)} name={`Grand titre ${i + 1}`}>
					<GrandTitre e={e} video={p.video} />
				</Sequence>
			))}
			<SousTitres legendes={p.legendes} fondClair={p.fondClair} masque={masque} />
			{de('accroche').map((e, i) => (
				<Sequence key={`a${i}`} {...seq(e)} name="Accroche">
					<Accroche e={e} fondClair={p.fondClair} />
				</Sequence>
			))}
			{de('icone').map((e, i) => (
				<Sequence key={`i${i}`} {...seq(e)} name={`Icône ${e.icone}`}>
					<Icone e={e} fondClair={p.fondClair} />
				</Sequence>
			))}
			{de('compteur').map((e, i) => (
				<Sequence key={`n${i}`} {...seq(e)} name={`Compteur ${e.valeur}`}>
					<Compteur e={e} />
				</Sequence>
			))}
			{de('transition')
				.filter((e) => e.style === 'lumiere')
				.map((e, i) => (
					<Sequence key={`l${i}`} from={Math.round((e.debut - 0.45) * fps)} durationInFrames={Math.round(0.9 * fps)} name="Lumière">
						<Lumiere />
					</Sequence>
				))}
			<Chapitres chapitres={p.chapitres} duree={p.duree} fondClair={p.fondClair} />
			{de('fin').map((e, i) => (
				<Sequence key={`f${i}`} {...seq(e)} name="Carte de fin">
					<CarteFin e={e} />
				</Sequence>
			))}
			{(p.ambiance.grain ?? 0.05) > 0 ? <Grain force={p.ambiance.grain ?? 0.05} /> : null}
			<Sons effets={p.effets} />
			<Musique p={p} />
		</AbsoluteFill>
	);
};
