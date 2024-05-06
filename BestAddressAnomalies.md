# Contexte

Le script/notebook Python BestAddressAnomalies.ipynb a pour but de mettre en évidence un certain nombre d'anomalies que l'on retrouve dans les données de BestAddress (Bosa), en se basant sur les CSV mis à disposition sur https://opendata.bosa.be/

Il s'agit ici de résultats prélimilaires, ayant pour objectif de montrer l'intérêt des techniques de GIS Analytics dans ce contexte de Data Quality.

Quatre types d'analyse distinctes sont menées : 
- Dans la première, nous regardons si toutes numéros de boite d'une même adresse sont bien localisés proches l'un de l'autre
- Dans la deuxième, nous comparons les frontières des codes postaux définis par bPost avec les codes postaux des adresses BestAddreses, ainsi que les frontières des codes NIS fournis par StatBel.
- Dans la troisième, nous recherchons des incohérences sur des noms de rues géographiquement proches (par exemple une "Rue Roi Albert I" juste à côté d'une "Rue du Roi Albert I")
- Dans la quatrième, nous recherchons des anomalies géométriques dans la forme d'une rue (plus précisément l'ensemble des adresses de même parité)

Principal résultat à retenir:
- +/- 17.000 adresses ont un code postal incohérent avec les contours des codes postaux définis par bPost. Étonnamment, il semble qu’il n’y ait aucune incohérence par rapport au code NIS;
- On trouve une centaine de rues dont l’orthographe diffère légèrement entre plusieurs tronçons (pair vs impair, ou au passage d’un code postal à l’autre);
- Sans doute plusieurs centaines d’adresses qui ne sont pas localisées au bon endroit (il faudra une exploration plus approfondie pour en connaitre le nombre plus précis).


Notons que nous ne gardons que les adresses ayant un statut "current" pour les analyses ci-dessous. Les "retired" (7.6% VLG ; <0.1% BRU ; 0% WAL ) et "proposed" (1.1 % VLG ; 0% BRU et WAL) sont ignorées. 
Nous ignorons également les adresses n'ayant aucun chiffre dans le "house_number" (< 60 addresses VLG, de type "ZN"). 



## Incohérence de boites

Nous regardons ici pour chaque adresse (rue, nis, code postal, numéro) si les coordonnées de "box number" ne sont pas anormalement éloignées. Dans un grande majorité des cas, les différentes boites auront toutes les mêmes coordonnées, mais ça n'est pas toujour le cas.

Notons que pour chaque adresse avec une boite, nous trouvons toujours (mise à part un très petit nombre d'exceptions, ~5 sur l'ensemble des 3 datasets) une adresse équivalente (même rue, nis, code postal, numéro) sans boite.

Dans un premier temps, pour chaque adresse avec des coordonnées différentes pour les boites, nous construisions l'enveloppe convexe englobant les différents points, et mettions en évidence ceux où le périmètre est très grand. Le problème de cette approche est que pour des résidences, il est fréquent d'avoir des boites réparties sur une grande superficie, avec donc un grand périmètre.

Nous construisons maintenant le "minimum rotated rectangle", à savoir le rectangle de surface minimal englobant l'ensemble des points, en autorisant toute rotation du rectangle. Un tel rectangle englobant deux points aura une largeur nulle et une longueur équivalente à la distance entre les points. En cas de points multiples non alignés, les deux dimensions seront positive.
De façon à éliminer les résidences, on sélectionnera les numéros donc la largeur du "minimum rotated rectangle" est d'au moins 100 mètres, et la largeur inférieure à 100 mètres.

Les anomalies ont essentiellement été détectées en VLG, avec plus de 100 cas (BRU: 3, WAL: 0).

## Frontières postales

Dans cette analyse, nous comparons les frontières des codes postaux définies par bPost (https://bgu.bpost.be/assets/9738c7c0-5255-11ea-8895-34e12d0f0423_x-shapefile_3812.zip). 
Pour ce faire, pour chaque adresse de Best, on regarde dans quel polygône de bPost il tombe et on retient ceux pour lequel il y a une inconsistance entre de code postal de Best et celui de bPost.

Pour éviter les problèmes de précision d'un point qui serait juste à la frontière, on supprime des contours de bPost un ruban de 50 mètres. On identifie donc un inconsistance que quand une adresse d'un code postal P1 != P2 (selon Best) est réellement dans le polygone d'un code postal P2 (selon bPost). 

Dans chaque page du fichier "best_anomalies_[region]_zip_mismatches.pdf", on peut voir :
- En titre, le code auquel Best associe tous les points de la carte
- Le tracé rouge indique le polygone de ce code postal selon bPost. S'il n'est pas présent, c'est que le code postal est inconnu de bPost (en tout cas de son shapefile)
- Chaque point représente les adresses Best incohérentes avec bPost. Sa couleur indique le code postal qu'il devrait avoir selon bPost

On trouve : 
- WAL: ~7880 anomalies
- BRU: ~75 anomalies
- VLG: ~11.000 anomalies
    
Notons que certains anomalies sont acceptables, comme par exemple le cas de batiments (chateau, ferme...) loin de la porte d'entrée. Best localise le batiment, mais son code postal correspond à celui de son entrée.

## Frontières de codes NIS

De façon quasi identique, nous comparons la colonne "municipality_id" avec les codes frontières des NIS définis sur https://statbel.fgov.be/sites/default/files/files/opendata/Statistische%20sectoren/sh_statbel_statistical_sectors_31370_20200101.shp.zip ;
Nous remarquons nettement moins d'anomalies qu'avec le code postal. Les seules anomalies observées se situent très proches des frontières.

## Incohérences de noms
    
Pour cette analyse, nous commençons par identifier la liste de tous les couples de rues adjacentes (c'est-à-dire que l'une a une adresse distante de moins de 100 mètres d'une adresse de l'autre). Nous regardons ensuite si l'on ne trouve pas de petites différences dans les noms de rue. 
Nous rencontrons typiquement deux situations : 
- Des rues traversant plusieurs communes avec une orthographe différente dans chacune d'elle : "Rue de Monténégro, 1060", vs "Rue du Monténégro, 1190"
- Des rues avec deux orthographes différentes au sein de la même commune: "Chaussée Brunehault" ou "Chaussée Brunehaut", à 4452 dans les 2 cas


On trouvera également quelques faux positifs: "Rue de Mars" vs "Rue de Mai". 

On élimine des listings les noms identiques à part une dernière lettre isolée ("Hensel laan A" vs "Hensel laan B"), ainsi que les noms où seul un chiffre change ("5de Zijweg" vs "6de Zijweg")

Nous générons deux fichiers distings : un quand la différence s'observe au sein d'une même commune (best\_anomalies\_[region]\_close\_streetnames\_same\_nis.pdf), un autre lorsqu'il s'agit de graphies différentes entre deux communes voisines (best\_anomalies\_[region]\_close\_streetnames\_diff\_nis.pdf)


## Géometrie incohérente

Nous considérons ici la forme géométrique composée de la séquence de points des adresses de même parité, pour une même rue et un même code postal. Sur cette ligne, nous calculons ensuite un certain nombre de métriques, en supposant que les valeurs les plus élevées dénotent une anomalie.

Nous avons défini de façon expérimentale un certain nombre de métriques. Il y a clairement de la redondance entre elles. Elle pourront encore être rafinées/développées par la suite

### dist_to_prev

Nous calculons ici pour chaque bloc (ensemble des adresses de même rue, même code postal et même parité de numéro de maison, triées par numéro) la distance maximale entre deux numéros consécutifs. 
Une valeur anormalement grande dénote : 
- Soit une situation normale, avec de  routes de campagnes ayant de longs segments sans adresses, ou des rues qui changent de code postal pour en revenir
- Soit une situation anormale, avec une (ou plusieurs) adresse(s) localisée(s) loin des autres de la même rue

### delta_dist_to_prev

De façon à distinguer une situation où toutes les adresses successives sont distantes de 1 km à une situation où toutes les adresses sont distantes de 10 mètres, sauf une distante de 1km, nous calculons ici une petite variante : il s'agit de diviser la distance maximale entre deux numéros successifs par la distance médiane entre deux numéros successifs du même bloc.

### prev_to_prev2_ratio

On s'attend en général à ce qu'un numéro soit plus proche du numéro suivant (de même parité) que celui d'encore après. Si le numéro 2 et beaucoup plus proche du 6 que du 4, il est probable que le 4 soit mal placé.
On calcule ici le ratio de la distance d'un numéro au numéro précédent (par ex. entre 4 et 6) sur la distance entre ce numéro et celui qui précède le précédant (par ex. entre 2 et 6). Une valeur de 100 indique donc qu'un numéro (indiqué un 'hn: ...' dans le titre du graphique) est 100 fois plus proche de deux numéros en arrière que du numéro précédent.

### sinuosity

On définit par "sinuosité" le rapport entre la longueur d'une courbe et le distance (en ligne droite) entre ses deux extrémités. Elle sera donc de 1 pour une courbe droite, et d'une valeur plus élevée si la courbe effectue un grand nombre de "détours".

### sw_sinuosity

Si entre deux points distants d'un km, on effectue une très longue boucle de 10km bien régulière (en roulant donc quasi tout droit), on aura la même sinuosité qu'en parcourant 10km en passant par d'innombrable petits virages très serrés, voire en faisant 5 allers-retours entre les 2 points. 
Pour distinguer ces situations, on calcule ici la moyenne de la sinuosité sur une fenêtre glissante de 5 numéros successifs.

### length

Cette mesure consiste simplement à mesurer la longueur total de la courbe. Une longueur anormalement grande dénote souvent une rue dans laquelle au moins une adresse a été erronément localisée à une grande distance des autres.  

### delta_ratio

Pour chaque couple d'adresses d'une même rue et de même parité, on calcule ici le ratio entre la différence entre la partie numérique des numéros de maison et la distance. Une valeur élevée indique que deux maisons de numéros très distants sont anormalement proches.
Ceci s'explique souvent par deux phénomènes distincts: 
- Situation normale : une rue "circulaire", dans laquelle le dernier numéro se situe à côté du premier
- Situation anormale : sur le coin entre deux rues, un batiment a été assigné à la mauvaise rue

### Liste consolidée

Dans le fichier "best_anomalies_[region]_consolidated.pdf", on retrouvera la liste de tous les blocs de rue se situant dans le top 50 d'au moins une des métriques présentées ci-desssus.
Pour chaque bloc, on trouve une première page avec la liste des adresses consistuant le bloc. Sur la seconde page, on verra l'ensemble adresses du bloc en question. La couleur indique l'ordre: en mauve le plus petit numéro, en jaune le plus grand. Dans le tableau en dessous de la carte, on retrouve les différentes métriques. Si applicable, la ligne "house_number" indique à quel niveau la métrique a été obtenue. La ligne "ranking" indique le rang du bloc pour la métrique.

