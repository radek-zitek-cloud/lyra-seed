import random

subjects = [
    "The cat",
    "A teacher",
    "My neighbor",
    "The programmer",
    "An artist",
    "The child",
    "A scientist",
]

verbs = [
    "builds",
    "finds",
    "writes",
    "observes",
    "carries",
    "likes",
    "discovers",
]

objects = [
    "a small robot",
    "an interesting book",
    "the red bicycle",
    "a strange idea",
    "a cup of tea",
    "the old map",
    "a bright star",
]

adverbs = [
    "quickly",
    "carefully",
    "happily",
    "silently",
    "eagerly",
    "gracefully",
    "curiously",
]


def generate_sentence():
    subject = random.choice(subjects)
    verb = random.choice(verbs)
    obj = random.choice(objects)
    adverb = random.choice(adverbs)
    return f"{subject} {verb} {obj} {adverb}."


if __name__ == "__main__":
    print(generate_sentence())
