import version1
import version2
from hypothesis import given, strategies as st

"""

Questions:
1: how do we get version 1 and version 2 during the running
2: how do we import version 1 and version 2 during running
3: how do we expand the tests to work for more inputs (way later ntm)

"""

def main():

    print("Testing Round 1: Basic Tests")
    test1through10()
    print("Passed!\n")

    print("Testing Round 2: Negatives")
    testNeg1through10()
    print("Passed!\n")


    print("Testing Round 3: All nums")
    testGen()
    print("Passed!\n")
    print("All tests passed :3\nRefactor is functionally the same")


@given(
        num1=st.integers(min_value=1, max_value=10),
        num2=st.integers(min_value=1, max_value=10))
def test1through10(num1, num2):
    ans1 = version1.add(num1, num2)
    ans2 = version2.add(num1, num2)

    assert(ans1 == ans2)

@given(
        num1=st.integers(min_value=-10, max_value=-1),
        num2=st.integers(min_value=-10, max_value=-1))
def testNeg1through10(num1, num2):
    ans1 = version1.add(num1, num2)
    ans2 = version2.add(num1, num2)

    assert(ans1 == ans2)

@given(
        num1=st.integers(),
        num2=st.integers())
def testGen(num1, num2):
    ans1 = version1.add(num1, num2)
    ans2 = version2.add(num1, num2)

    assert(ans1 == ans2)




if __name__ == "__main__":
    # run the property test
    main()
    print("passed")