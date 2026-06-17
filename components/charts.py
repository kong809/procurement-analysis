import plotly.express as px
import plotly.graph_objects as go


def bar_chart(df, x, y, title="", color=None, orientation="v"):
    fig = px.bar(df, x=x, y=y, title=title, color=color, orientation=orientation)
    fig.update_traces(texttemplate="%{y:.2f}", textposition="outside")
    fig.update_layout(margin=dict(l=10, r=10, t=25, b=40), height=190, xaxis_tickangle=-30)
    return fig


def pie_chart(df, values, names, title="", hole=0.4):
    fig = px.pie(df, values=values, names=names, hole=hole)
    fig.update_traces(textposition="inside", textinfo="label+percent",
                      texttemplate="%{label}<br>%{percent:.1%}")
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=200, showlegend=False)
    return fig


def grouped_bar_chart(df, x, y, color, title="", barmode="group"):
    fig = px.bar(df, x=x, y=y, color=color, barmode=barmode, title=title)
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig


def stacked_bar_top_n(df, category_col, value_col, top_n=20, title=""):
    top = df.nlargest(top_n, value_col)
    fig = px.bar(top, x=category_col, y=value_col, title=title or f"Top {top_n}")
    fig.update_layout(margin=dict(l=20, r=20, t=40, b=20))
    return fig
