name = "Tom"
score = 7 + 5 * 2
print(f"Hello {name}, your score is {score}")
if score >= 15:
    print(f"Passed with {score}")
for _ in range(int(3)):
    print(f"Loop {1 + 1}")
def greet(who):
    print(f"Hi {who}!")
greet(name)
