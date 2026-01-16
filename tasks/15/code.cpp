#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int q;
    if(!(cin>>q)) return 0;

    vector<long long> st, mn;

    while(q--) {

        string op;
        cin>>op;

        if(op=="push") {
            long long x;
            cin>>x;
            st.push_back(x);

            if(mn.empty() || x < mn.back()) mn.push_back(x);

        }
        else if(op=="pop") {
            if(!st.empty()) st.pop_back();
        }

        else if(op=="min") {
            if(mn.empty()) cout<<"0\n";
            else cout<<mn.back()<<"\n";
        }

    }

}
