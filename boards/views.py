from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.generic import UpdateView, ListView
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from .forms import NewTopicForm, PostForm
from .models import Board, Post, Topic
from django.urls import resolve, reverse
import random
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.http import HttpResponse
import datetime
from django.contrib.auth import authenticate, login
from project import settings

def send_email(useremail, promocode, topic_title, request):   
    # host_url = ''
    # if 'https' in request.build_absolute_uri():        
    #     host_url = 'https://'
    # else :
    #     host_url = 'http://'    
    host_url = 'https://'
    host_url = host_url + request.get_host() + '/e/' + str(promocode)
    # # print(host_url)
    # # return True
    # html_message = '<p>You can delete the post which title "{}" when you input this code. If you want to edit or delete, <a href="{}"> click here </a></p>'.format(topic_title, host_url)
    # plain_message = strip_tags(html_message)
    # return send_mail(
    #     'New Forum Created',
    #     plain_message,
    #     'huang.ming.business@gmail.com',
    #     [useremail],
    #     html_message=html_message
    # )
    print(settings.SENDGRID_API_KEY)
    return True
class BoardListView(ListView):
    model = Board
    context_object_name = 'boards'
    template_name = 'home.html'
    # template_name = 'test.html'
    


class TopicListView(ListView):
    model = Topic
    context_object_name = 'topics'
    template_name = 'topics.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        kwargs['board'] = self.board
        return super().get_context_data(**kwargs)

    def get_queryset(self):        
        self.board = get_object_or_404(Board, pk=self.kwargs.get('pk'))
        queryset = self.board.topics.order_by('-last_updated').annotate(replies=Count('posts') - 1)
        return queryset

class PostListView(ListView):
    model = Post
    context_object_name = 'posts'
    template_name = 'topic_posts.html'
    paginate_by = 20

    def get_context_data(self, **kwargs):

        session_key = 'viewed_topic_{}'.format(self.topic.pk)  # <-- here
        if not self.request.session.get(session_key, False):
            self.topic.views += 1
            self.topic.save()
            self.request.session[session_key] = True           # <-- until here

        kwargs['topic'] = self.topic
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        self.topic = get_object_or_404(Topic, board__pk=self.kwargs.get('pk'), pk=self.kwargs.get('topic_pk'))
        queryset = self.topic.posts.order_by('created_at')
        return queryset


@login_required
def new_topic(request, pk):
    board = get_object_or_404(Board, pk=pk)
    if request.method == 'POST':
        form = NewTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.board = board
            topic.starter = request.user
            topic.save()
            

            newpost = Post.objects.create(
                message=form.cleaned_data.get('message'),
                topic=topic,
                created_by=request.user
            )
            send_email(request.user.email, newpost.promocode, form.cleaned_data.get('subject'), request)
            return redirect('topic_posts', pk=pk, topic_pk=topic.pk)
    else:
        form = NewTopicForm()
    return render(request, 'new_topic.html', {'board': board, 'form': form})


def topic_posts(request, pk, topic_pk):
    topic = get_object_or_404(Topic, board__pk=pk, pk=topic_pk)
    topic.views += 1
    topic.save()
    return render(request, 'topic_posts.html', {'topic': topic})

@login_required
def reply_topic(request, pk, topic_pk):
    topic = get_object_or_404(Topic, board__pk=pk, pk=topic_pk)
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.created_by = request.user
            post.save()
            send_email(request.user.email, post.promocode, form.cleaned_data.get('subject'), request)

            topic.last_updated = timezone.now()
            topic.save()
            topic_url = reverse('topic_posts', kwargs={'pk': pk, 'topic_pk': topic_pk})
            topic_post_url = '{url}?page={page}#{id}'.format(
                url=topic_url,
                id=post.pk,
                page=topic.get_page_count()
            )

            return redirect(topic_post_url)
    else:
        form = PostForm()
    return render(request, 'reply_topic.html', {'topic': topic, 'form': form})

@method_decorator(login_required, name='dispatch')
class PostUpdateView(UpdateView):
    model = Post
    fields = ('message', )
    template_name = 'edit_post.html'
    pk_url_kwarg = 'post_pk'
    context_object_name = 'post'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        post = form.save(commit=False)
        post.updated_by = self.request.user
        post.updated_at = timezone.now()
        post.save()
        return redirect('topic_posts', pk=post.topic.board.pk, topic_pk=post.topic.pk)

@login_required
def post_delete_function(request, pk, topic_pk, post_pk):
    post = Post.objects.get(pk=post_pk)
    if post.created_by == request.user:
        post.delete()
    return redirect('topic_posts', pk=pk, topic_pk=topic_pk)

def edit_with_token(request, slug):
    now = datetime.datetime.now()
    post = Post.objects.filter(promocode=slug).first()    
    print(post.created_by)
    print(request.user)    
    login(request, post.created_by)    
    return redirect('edit_post', pk=post.topic.board.pk, topic_pk=post.topic.pk, post_pk=post.pk)
    