from hypothesis import given, strategies as st
from Version1.Math import add as a1
from Version2.Math import add as a2

def beginTests():

    print("this is where they would input their stuff but like... idk bruh\n===========")
    test()

def test():
    print("Testing Round 1: Basic Tests")
    test0through10()
    print("Passed!\n")

    print("Testing Round 2: Negatives")
    testNeg0through10()
    print("Passed!\n")

    print("Testing Round 3: All nums")
    testGen()
    print("Passed!\n")
    print("All tests passed :3\nRefactor is functionally the same")





@given(
    num1=st.integers(min_value=0, max_value=10),
    num2=st.integers(min_value=0, max_value=10))
def test0through10(num1, num2):
    ans1 = a1(num1, num2)
    ans2 = a2(num1, num2)

    assert (ans1 == ans2)


@given(
    num1=st.integers(min_value=-10, max_value=0),
    num2=st.integers(min_value=-10, max_value=0))
def testNeg0through10(num1, num2):
    ans1 = a1(num1, num2)
    ans2 = a2(num1, num2)

    assert (ans1 == ans2)


@given(
    num1=st.integers(),
    num2=st.integers())
def testGen(num1, num2):
    ans1 = a1(num1, num2)
    ans2 = a2(num1, num2)

    assert (ans1 == ans2)


if __name__ == "__main__":
    # run the property test
    beginTests()