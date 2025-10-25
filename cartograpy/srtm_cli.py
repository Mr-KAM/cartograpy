"""
Interface en ligne de commande pour SRTM Downloader
"""
import argparse
import sys
import getpass
from cartograpy.srtm_core import SRTMDownloader


def main():
    """Point d'entrée principal pour la CLI."""
    parser = argparse.ArgumentParser(
        description="Télécharge des tuiles SRTM depuis les serveurs NASA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Exemples:
        # Télécharger une zone en France
        srtm-downloader -u USERNAME -p PASSWORD -w 2.0 -e 3.0 -s 48.5 -n 49.5 -o ./data
        
        # Télécharger en mode interactif (sans mot de passe en clair)
        srtm-downloader -u USERNAME -w 2.0 -e 3.0 -s 48.5 -n 49.5 -o ./data

        Note: Vous devez avoir un compte NASA Earthdata (gratuit):
            https://urs.earthdata.nasa.gov/users/new
        """
    )
    
    # Arguments obligatoires
    parser.add_argument(
        '-u', '--username',
        required=True,
        help="Nom d'utilisateur NASA Earthdata"
    )
    
    parser.add_argument(
        '-p', '--password',
        help="Mot de passe NASA Earthdata (si omis, sera demandé de manière sécurisée)"
    )
    
    # Zone géographique
    parser.add_argument(
        '-w', '--west',
        type=float,
        required=True,
        help="Longitude ouest (limite gauche de la zone)"
    )
    
    parser.add_argument(
        '-e', '--east',
        type=float,
        required=True,
        help="Longitude est (limite droite de la zone)"
    )
    
    parser.add_argument(
        '-s', '--south',
        type=float,
        required=True,
        help="Latitude sud (limite basse de la zone)"
    )
    
    parser.add_argument(
        '-n', '--north',
        type=float,
        required=True,
        help="Latitude nord (limite haute de la zone)"
    )
    
    # Arguments optionnels
    parser.add_argument(
        '-o', '--output',
        default='./srtm_data',
        help="Répertoire de sortie (défaut: ./srtm_data)"
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help="Re-télécharger les fichiers existants"
    )
    
    parser.add_argument(
        '--resolution',
        choices=['1arc', '3arc'],
        default='1arc',
        help="Résolution des données (défaut: 1arc ~30m)"
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='SRTM Downloader 3.2.3'
    )
    
    args = parser.parse_args()
    
    # Demander le mot de passe de manière sécurisée si non fourni
    password = args.password
    if not password:
        try:
            password = getpass.getpass("Mot de passe NASA Earthdata: ")
        except KeyboardInterrupt:
            print("\n\n❌ Opération annulée par l'utilisateur")
            sys.exit(1)
    
    # Validation des coordonnées
    if args.west >= args.east:
        print("❌ Erreur: --west doit être inférieur à --east")
        sys.exit(1)
    
    if args.south >= args.north:
        print("❌ Erreur: --south doit être inférieur à --north")
        sys.exit(1)
    
    # Validation de la zone SRTM
    if args.north > 60 or args.south < -56:
        print("⚠️  Attention: Les données SRTM couvrent uniquement 60°N à 56°S")
        if args.north > 60 and args.south > 60:
            print("❌ La zone est entièrement hors de la couverture SRTM")
            sys.exit(1)
        if args.south < -56 and args.north < -56:
            print("❌ La zone est entièrement hors de la couverture SRTM")
            sys.exit(1)
    
    print("=" * 60)
    print("   SRTM DOWNLOADER v3.2.3")
    print("=" * 60)
    print(f"📍 Utilisateur: {args.username}")
    print(f"📂 Répertoire de sortie: {args.output}")
    print(f"📐 Résolution: {args.resolution}")
    print("=" * 60)
    
    try:
        # Créer le téléchargeur
        downloader = SRTMDownloader(
            username=args.username,
            password=password,
            resolution=args.resolution
        )
        
        # Télécharger la zone
        files = downloader.download_area(
            west=args.west,
            east=args.east,
            south=args.south,
            north=args.north,
            output_dir=args.output,
            overwrite=args.overwrite
        )
        
        if files:
            print("\n" + "=" * 60)
            print("✅ TÉLÉCHARGEMENT RÉUSSI")
            print("=" * 60)
            print(f"📁 Fichiers téléchargés: {len(files)}")
            print(f"📂 Emplacement: {args.output}")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ ÉCHEC DU TÉLÉCHARGEMENT")
            print("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n❌ Téléchargement interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
