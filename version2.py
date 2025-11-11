from hypothesis import given, strategies as st

#addition
#def add(num1, num2):
#    return num1+num2

#refactor w/ same answer
def add(num1, num2):
    ans = num1 * num2
    return ans
@given(
    num1 = st.integers(min_value=1, max_value=10),
    num2 = st.integers(min_value=1, max_value=10))
def test(num1, num2):
    assert add(num1, num2) == num1 + num2


#refactor w/ different answer
#def add(num1, num2):
#    sum = num1 + num2
#    return num2 #returning second input instead of answer
