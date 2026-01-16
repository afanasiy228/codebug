#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if(!(cin>>s)) return 0;
    int n=s.size();
    vector<int> pi(n,0);

    for(int i=1;i<n;i++) {
        int j=pi[i-1];
        while(j>0 && s[i]!=s[j]) j=pi[j-1];
        if(s[i]==s[j]) j++;
        pi[i]=j;
    }

    cout<<pi[n-1]-1<<"\n";

}
