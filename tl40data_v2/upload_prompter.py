import datetime
import sys
try:
    import tomllib as toml
except ImportError:
    try:
        import toml
    except ImportError:
        print("You need to do a `pip3 install toml`...")
        sys.exit(1)

with open("config.toml", 'r') as fr:
    config = toml.load(fr)


# Load current upload-months from config; fill month values
to_upload = []
months = []
month_idx = datetime.date.today().replace(day=1)
for x in range(13):
    key = f"m{x}"
    to_upload.append(config["months"].get(key, 0))
    months.append(month_idx.strftime("%Y-%m.html"))
    # Update date object to next prior month
    if month_idx.month == 1:
        month_idx = month_idx.replace(year=month_idx.year - 1, month=12)
    else:
        month_idx = month_idx.replace(month=month_idx.month - 1)

months[0] = "index.html"

while True:
    for x in range(13):
        print(f"{x+1:2} : {'✓' if to_upload[x] else ' '} {months[x]}")
    print("d : Done")
    print("a : Select all")
    print("c : Clear/reset")

    answer = input("Enter 'd' if the above is fine, or a number to toggle uploading that month. 'a' to upload all, 'c' to clear and upload none.\n").strip().lower()

    if answer == 'd':
        break
    elif answer == 'a':
        to_upload = [1]*len(to_upload)
    elif answer == 'c':
        to_upload = [0]*len(to_upload)
    else:
        try:
            answer = int(answer)
            if 1 > answer or answer > len(months):
                print("Invalid selection")
                continue
            to_upload[answer-1] = 0 if to_upload[answer-1] else 1
        except ValueError:
            print("Invalid selection")
            continue

with open("upload_list.txt", 'w') as fw:
    for idx, month in enumerate(months):
        if to_upload[idx]:
            fw.write("html/" + month + " ")

print("Done! Wrote upload list to upload_list.txt.")
