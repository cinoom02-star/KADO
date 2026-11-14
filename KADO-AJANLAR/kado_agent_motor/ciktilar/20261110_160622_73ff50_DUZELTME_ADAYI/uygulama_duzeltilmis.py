import random

def run_game():
    print("Sayi tahmin oyununa hos geldin!")
    secret_number = random.randint(1, 100)
    attempts = 0

    while True:
        try:
            guess = int(input("1 ile 100 arasinda bir sayi gir: "))
        except ValueError:
            print("Lutfen gecerli bir tam sayi gir.")
            continue

        if not 1 <= guess <= 100:
            print("Sayi 1 ile 100 arasinda olmali.")
            continue

        attempts += 1

        if guess < secret_number:
            print("Daha buyuk bir sayi dene.")
        elif guess > secret_number:
            print("Daha kucuk bir sayi dene.")
        else:
            print(f"Tebrikler! {attempts} denemede bildin.")
            break

if __name__ == "__main__":
    run_game()
